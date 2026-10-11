"""Distributed Training From Scratch — course manifest.

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

    python3 codecraft/cli.py run distributed-training-from-scratch
"""

from codecraft.api import stage

TITLE = "Distributed Training From Scratch"
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
        for candidate_start in (os.environ.get("H1_REPO"), start, os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "distributed-training-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set H1_REPO=/path/to/learn-stuff-from-scratch")

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

    import dataclasses

    import fabric
    import model
    import plans

    import stage_01 as s

    # ---- the frozen shapes -------------------------------------------------

    assert [field.name for field in dataclasses.fields(s.Collective)] == [
        "axis", "name", "group", "length", "algo", "plan"], (
        "Collective's fields are %r, not the frozen (axis, name, group, length, "
        "algo, plan)" % ([field.name for field in dataclasses.fields(s.Collective)],))
    assert [field.name for field in dataclasses.fields(s.MemoryLine)] == [
        "what", "group", "bytes"], (
        "MemoryLine's fields are %r, not the frozen (what, group, bytes)"
        % ([field.name for field in dataclasses.fields(s.MemoryLine)],))
    assert [field.name for field in dataclasses.fields(s.StepPlan)] == [
        "collectives", "compute", "memory"], (
        "StepPlan's fields are %r, not the frozen (collectives, compute, memory)"
        % ([field.name for field in dataclasses.fields(s.StepPlan)],))

    ring4 = fabric.ring(4)
    probe = s.Collective("dp", "grads", ("r0", "r1"), 4, "ring",
                         fabric.Plan(transfers=()))
    assert (probe.axis, probe.name, probe.group, probe.length, probe.algo) == (
        "dp", "grads", ("r0", "r1"), 4, "ring"), (
        "a Collective's fields read %r, not the frozen values"
        % ((probe.axis, probe.name, probe.group, probe.length, probe.algo),))
    try:
        probe.length = 5
    except dataclasses.FrozenInstanceError:
        pass
    else:
        raise AssertionError(
            "a Collective is mutable: a plan must be frozen data, but "
            "probe.length took the value 5")

    line_probe = s.MemoryLine("optimizer", ("r0", "r1"), 8)
    assert (line_probe.what, line_probe.group, line_probe.bytes) == (
        "optimizer", ("r0", "r1"), 8), (
        "a MemoryLine's fields read %r, not the frozen values" % (line_probe,))

    # ---- plan_bytes: the per-rank figure, and only it ----------------------

    world4 = fabric.full(4)
    g4 = world4.ranks
    all4 = plans.ring_allreduce(world4, g4, 100)
    assert fabric.legality_problems(world4, all4) == (), (
        "the fixture is not legal: %r" % (fabric.legality_problems(world4, all4),))
    c4 = s.Collective("dp", "grads", g4, 100, "ring", all4)
    step_one = s.StepPlan(collectives=(c4,), compute=0, memory=())

    assert s.plan_bytes(step_one) == 400, (
        "a collective of 100 elements costs %r bytes per rank, not 400: the "
        "per-rank figure is what one rank moves, not the whole network's"
        % (s.plan_bytes(step_one),))
    assert s.network_bytes(step_one) == 1600, (
        "a 100-element collective over four ranks puts %r bytes on the network, "
        "not 4 * 400: the network figure is the per-rank figure times the group "
        "size" % (s.network_bytes(step_one),))

    all4b = plans.ring_allreduce(world4, g4, 50)
    c4b = s.Collective("tp", "activations", g4, 50, "ring", all4b)
    step_two = s.StepPlan(collectives=(c4, c4b), compute=0, memory=())
    assert s.plan_bytes(step_two) == 600, (
        "the two collectives of 100 and 50 elements cost %r bytes per rank, not "
        "400 + 200: a plan is the sum of its collectives' per-rank bytes"
        % (s.plan_bytes(step_two),))
    assert s.network_bytes(step_two) == 2400, (
        "the same two collectives put %r bytes on the network, not 1600 + 800"
        % (s.network_bytes(step_two),))

    step_empty = s.StepPlan(collectives=(), compute=0, memory=())
    assert s.plan_bytes(step_empty) == 0 and s.network_bytes(step_empty) == 0, (
        "an empty plan moves %r bytes per rank and %r on the network, not 0"
        % (s.plan_bytes(step_empty), s.network_bytes(step_empty)))

    # ---- plan_memory: the ledger, divided per group ------------------------

    tiny = model.SHAPES["tiny"]
    assert tiny.params() == 388, "the fixture changed: tiny has %d params" % (tiny.params(),)

    want = (
        s.MemoryLine("params", g4, 194),
        s.MemoryLine("gradients", g4, 194),
        s.MemoryLine("masters", g4, 388),
        s.MemoryLine("optimizer", g4, 776),
    )
    lines = s.plan_memory(tiny, step_one)
    assert lines == want, (
        "the ledger of a four-rank plan is %r, not %r: every rank holds a "
        "quarter of each kind, and there are four kinds (16 B/param, not 4)"
        % (lines, want))
    assert sum(item.bytes for item in lines) == 1552, (
        "the ledger totals %r bytes per rank, not 16 * 388 / 4: the kinds are "
        "2 + 2 + 4 + 8 bytes per parameter"
        % (sum(item.bytes for item in lines),))

    world3 = fabric.full(3)
    g3 = world3.ranks
    all3 = plans.ring_allreduce(world3, g3, 100)
    assert fabric.legality_problems(world3, all3) == (), (
        "the three-rank fixture is not legal: %r"
        % (fabric.legality_problems(world3, all3),))
    c3 = s.Collective("dp", "grads", g3, 100, "ring", all3)
    step_three = s.StepPlan(collectives=(c3,), compute=0, memory=())
    lines3 = s.plan_memory(tiny, step_three)
    assert [item.bytes for item in lines3] == [259, 259, 518, 1035], (
        "a three-rank ledger reads %r, not [259, 259, 518, 1035]: a per-rank "
        "share that does not divide is ceiled, not floored"
        % ([item.bytes for item in lines3],))

    step_dup = s.StepPlan(collectives=(c4, c4b), compute=0, memory=())
    assert len(s.plan_memory(tiny, step_dup)) == 4, (
        "a plan naming one group twice has a %d-line ledger, not one line per "
        "(what, group)"
        % (len(s.plan_memory(tiny, step_dup)),))

    step_mixed = s.StepPlan(collectives=(c4, c3), compute=0, memory=())
    lines_mixed = s.plan_memory(tiny, step_mixed)
    assert len(lines_mixed) == 8 and lines_mixed[4].group == g3, (
        "a plan over two groups has %r ledger lines, not four per group in the "
        "order the groups appear" % (len(lines_mixed),))
    assert s.plan_memory(tiny, step_empty) == (), (
        "a plan with no collectives has ledger %r, not the empty ledger"
        % (s.plan_memory(tiny, step_empty),))

    # ---- plan_ticks: per byte, per hop, per step, summed -------------------

    one = fabric.send("r0", "r1", 100, 0)
    assert s.plan_ticks(ring4, fabric.Plan(transfers=(one,))) == 9, (
        "one hop of 400 bytes costs %r ticks, not 5 + ceil(400 / 100) = 9: the "
        "cost is per byte, and the element size was lost"
        % (s.plan_ticks(ring4, fabric.Plan(transfers=(one,))),))

    odd = fabric.send("r0", "r1", 30, 0)
    assert s.plan_ticks(ring4, fabric.Plan(transfers=(odd,))) == 7, (
        "30 elements (120 bytes) over a 100-byte/tick link cost %r ticks, not "
        "5 + ceil(120 / 100) = 7: the byte time is ceiled, not floored or "
        "rounded" % (s.plan_ticks(ring4, fabric.Plan(transfers=(odd,))),))

    two = fabric.send("r0", "r2", 100, 0)
    assert s.plan_ticks(ring4, fabric.Plan(transfers=(two,))) == 18, (
        "the same 400 bytes over the two hops r0-r1-r2 cost %r ticks, not "
        "2 * (5 + 4) = 18: a transfer is charged every hop, latency and bytes "
        "alike" % (s.plan_ticks(ring4, fabric.Plan(transfers=(two,))),))

    switch8 = fabric.switch(8, width=4)
    cross = fabric.send("r1", "r5", 400, 0)
    assert s.plan_ticks(switch8, fabric.Plan(transfers=(cross,))) == 104, (
        "the cross-group transfer cost %r ticks, not 10 + 84 + 10 = 104: a "
        "three-hop route is not one hop's cost"
        % (s.plan_ticks(switch8, fabric.Plan(transfers=(cross,))),))

    pmulti = fabric.Plan(transfers=(fabric.send("r0", "r1", 100, 0),
                                    fabric.send("r2", "r3", 300, 0)))
    assert s.plan_ticks(ring4, pmulti) == 17, (
        "a step holding a 9-tick and a 17-tick transfer cost %r ticks, not 17: "
        "a step costs its slowest transfer, not the sum of them"
        % (s.plan_ticks(ring4, pmulti),))

    ptwo = fabric.Plan(transfers=(fabric.send("r0", "r1", 100, 0),
                                  fabric.send("r1", "r2", 100, 1)))
    assert s.plan_ticks(ring4, ptwo) == 18, (
        "the two-step plan cost %r ticks, not 9 + 9 = 18: a plan is the sum of "
        "its steps" % (s.plan_ticks(ring4, ptwo),))

    p3 = fabric.Plan(transfers=(fabric.send("r0", "r1", 100, 0),
                                fabric.send("r0", "r2", 100, 1)))
    assert s.plan_ticks(ring4, p3) == 27, (
        "the plan of a 9-tick step and an 18-tick step cost %r ticks, not "
        "9 + 18 = 27: a step reads its own transfers, not every transfer in "
        "the plan" % (s.plan_ticks(ring4, p3),))

    assert s.plan_ticks(ring4, fabric.Plan(transfers=())) == 0, (
        "the empty plan cost %r ticks, not nothing"
        % (s.plan_ticks(ring4, fabric.Plan(transfers=())),))

    disconnected = fabric.Topology(
        ranks=("r0", "r1", "r2", "r3"),
        links=(fabric.Link(a="r0", b="r1", bandwidth=100, latency=5),))
    ghost = fabric.Plan(transfers=(fabric.send("r0", "r3", 4, 0),))
    message = _refuses(fabric.FabricError, "a plan with an unroutable transfer",
                       lambda: s.plan_ticks(disconnected, ghost))
    assert "r3" in message or "rout" in message, (
        "the refusal of an unroutable transfer does not name it: %r" % (message,))

    # ---- step_ticks: the maximum of compute and comms ----------------------

    twohop = fabric.Plan(transfers=(fabric.send("r0", "r2", 100, 0),))
    c_comm = s.Collective("dp", "grads", ring4.ranks, 100, "ring", twohop)
    c_one = s.Collective("tp", "activations", ring4.ranks, 100, "ring",
                         fabric.Plan(transfers=(fabric.send("r0", "r1", 100, 0),)))

    hop_plan = s.StepPlan(collectives=(c_comm,), compute=100, memory=())
    assert s.step_ticks(ring4, hop_plan) == 100, (
        "a step of 100 ticks of compute and 18 of comms costs %r ticks, not "
        "the maximum 100: comms overlap compute and are not added to it"
        % (s.step_ticks(ring4, hop_plan),))
    comm_plan = s.StepPlan(collectives=(c_comm,), compute=5, memory=())
    assert s.step_ticks(ring4, comm_plan) == 18, (
        "a step of 5 ticks of compute and 18 of comms costs %r ticks, not the "
        "maximum 18" % (s.step_ticks(ring4, comm_plan),))
    both_plan = s.StepPlan(collectives=(c_one, c_comm), compute=0, memory=())
    assert s.step_ticks(ring4, both_plan) == 27, (
        "a step of two collectives costing 9 and 18 ticks costs %r ticks, not "
        "9 + 18 = 27: the comms is the sum of the collectives' plan ticks"
        % (s.step_ticks(ring4, both_plan),))
    assert s.step_ticks(ring4, step_empty) == 0, (
        "the empty step costs %r ticks, not nothing"
        % (s.step_ticks(ring4, step_empty),))

    # ---- params_by_rank: the plan shards the remainder ---------------------

    assert s.params_by_rank(tiny, ranks=4) == (97, 97, 97, 97), (
        "388 parameters over four ranks are %r, not four equal 97s"
        % (s.params_by_rank(tiny, ranks=4),))
    assert s.params_by_rank(tiny, ranks=8) == (49, 49, 49, 49, 48, 48, 48, 48), (
        "388 parameters over eight ranks are %r, not 48 each plus the four "
        "remainder spread one at a time over the first ranks"
        % (s.params_by_rank(tiny, ranks=8),))
    assert s.params_by_rank(tiny, ranks=3) == (130, 129, 129), (
        "388 parameters over three ranks are %r, not 129 each plus the one "
        "remainder on the first rank"
        % (s.params_by_rank(tiny, ranks=3),))
    assert s.params_by_rank(tiny, ranks=1) == (388,), (
        "388 parameters over one rank are %r, not the whole set"
        % (s.params_by_rank(tiny, ranks=1),))

    wide = s.params_by_rank(tiny, ranks=512)
    assert isinstance(wide, tuple) and len(wide) == 512, (
        "512 ranks get %r, not a tuple of 512 shares" % (type(wide).__name__,))
    assert sum(wide) == 388, (
        "512 ranks hold %r parameters between them, not 388"
        % (sum(wide),))
    assert wide[387] == 1 and wide[388] == 0, (
        "the 388th rank holds %r and the 389th %r: a rank the parameter set "
        "does not reach is empty, not given a full share"
        % (wide[387], wide[388]))

    message = _refuses(model.ModelError, "a rank count below one",
                       lambda: s.params_by_rank(tiny, ranks=0))
    assert "ranks" in message, (
        "the refusal of a rank count below one does not name ranks: %r"
        % (message,))
    message = _refuses(model.ModelError, "a bool rank count",
                       lambda: s.params_by_rank(tiny, ranks=True))
    assert "ranks" in message, (
        "the refusal of a bool rank count does not name ranks: %r" % (message,))

    one_b = model.SHAPES["1b"]
    assert s.params_by_rank(one_b, ranks=8) == (136653056,) * 8, (
        "1b over eight ranks is %r, not eight equal quarters"
        % (s.params_by_rank(one_b, ranks=8),))

    print("check_01: the shapes and the ledger — a Collective, StepPlan and "
          "MemoryLine are frozen data, plan_bytes is per rank and network_bytes "
          "in total, plan_memory divides the state over the group, plan_ticks "
          "charges bytes and hops and sums steps, step_ticks overlaps compute "
          "and comms, and params_by_rank shards the remainder")

# --- stage 2 -----------------------------------------------------------------------
def check_2():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    FLOPS_PER_TICK = 1_000_000_000_000

    BUCKET = 25_000_000

    def _repo(start=None):
        for candidate_start in (os.environ.get("H1_REPO"), start, os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "distributed-training-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set H1_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call):
        """The message of the refusal `call` must raise, or the mistake named.

        A return, any other exception, or a stub's `NotImplementedError` is not a
        refusal: the first two are the mistake, the third must escape so an
        untouched template reads as `TODO`, not as a failed check.
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

    def _backward_rows(shape):
        """The check's own flat layout of the gradient.

        The backward pass fills the trainable tensors in *reverse* `tensors()`
        order, so the flat buffer's rows are `(name, offset, elements)` in that
        order. This is deliberately not read off the stage: a stage whose buckets
        are laid out forward has to be caught, not agreed with.
        """
        rows = []
        offset = 0
        for tensor in reversed(shape.tensors()):
            if not tensor.trainable:
                continue
            rows.append((tensor.name, offset, tensor.elements))
            offset += tensor.elements
        return tuple(rows)

    def _per_rank(plan):
        """The elements the busiest rank sends, recomputed from the plan itself."""
        sent = {}
        for transfer in plan.transfers:
            sent[transfer.src] = sent.get(transfer.src, 0) + transfer.length
        if not sent:
            return 0
        return max(sent.values())

    def _partial_gradients(shape, *, batch, seq, ranks):
        """Each rank's share of the step's gradient, by tensor name.

        Rank `i` holds the token block `[i*batch, (i+1)*batch)` of the step's
        `len(ranks) * batch` sequences, and the reference is a sum over tokens, so
        its share is the reference at the block's end minus the reference at its
        start (`reference_gradients` always counts from token zero, so the
        difference *is* the block). The shares telescope to the whole step's batch.
        """
        import model

        names = model.gradient_names(shape)
        shares = {}
        for index, rank in enumerate(ranks):
            high = model.reference_gradients(shape, batch=(index + 1) * batch, seq=seq)
            if index:
                low = model.reference_gradients(shape, batch=index * batch, seq=seq)
                high = tuple(a - b for a, b in zip(high, low))
            shares[rank] = dict(zip(names, high))
        return shares

    def _flat(shape, share):
        """One rank's per-tensor gradient, spread over the flat backward buffer.

        The reference's gradient is one int per tensor — the tensor's own value —
        so every element of the tensor's slice carries it, and the element-wise
        all-reduce's sum over that slice is what the reference reports.
        """
        flat = [0] * shape.params()
        for name, offset, elements in _backward_rows(shape):
            for slot in range(elements):
                flat[offset + slot] = share[name]
        return flat

    def _reduced(world, shape, shares, buckets):
        """Run every bucket's plan on the ranks' buffers and stitch the results.

        Returns the flat gradient every rank ends holding, or the mistake: the
        ranks must agree (an all-reduce leaves the sum on every member) and the
        plan must cover the buffer the buckets laid out.
        """
        import fabric

        group = tuple(world.ranks)
        flats = {rank: _flat(shape, shares[rank]) for rank in group}
        out = [0] * shape.params()
        for bucket in buckets:
            buffers = {}
            for rank in group:
                piece = tuple(flats[rank][bucket.offset:bucket.offset + bucket.length])
                buffers[rank] = piece + (0,) * (bucket.padded - bucket.length)
            result = fabric.run(world, bucket.plan, buffers, op="sum")
            rows = {tuple(values) for values in result.values()}
            assert len(rows) == 1, (
                "the reduction of bucket %d left the ranks holding %r different "
                "buffers, not the same element-wise sum on every member — it is not "
                "an all-reduce" % (bucket.index, len(rows)))
            row = next(iter(rows))
            for slot in range(bucket.length):
                out[bucket.offset + slot] = row[slot]
        return out

    def _semantics(shape, world, *, batch, seq, bucket_bytes=BUCKET):
        """Whether the plan's own buckets reduce the ranks' shares to the reference.

        The step's whole batch is `len(world.ranks) * batch` sequences; the
        reference gradient of the ranks' shares, all-reduced by the plan's buckets,
        must be `reference_gradients` at that batch, tensor by tensor, exactly.
        """
        import model

        import stage_02 as s

        group = tuple(world.ranks)
        shares = _partial_gradients(shape, batch=batch, seq=seq, ranks=group)
        buckets = s.bucket_schedule(shape, world, bucket_bytes=bucket_bytes)
        flat = _reduced(world, shape, shares, buckets)
        want = dict(zip(model.gradient_names(shape),
                        model.reference_gradients(shape, batch=batch * len(group),
                                                  seq=seq)))
        for name, offset, elements in _backward_rows(shape):
            slice_ = flat[offset:offset + elements]
            assert len(set(slice_)) == 1 and slice_[0] == want[name], (
                "after the all-reduce, %s holds %r, not the reference gradient %r of "
                "the whole step's %d sequences: a bucket left unreduced, reduced in "
                "the wrong order, or shifted cannot land on the reference"
                % (name, sorted(set(slice_))[:4], want[name],
                   batch * len(group)))
        return want, shares[group[0]]

    import dataclasses

    import fabric
    import model
    import plans

    import stage_01 as s1

    import stage_02 as s

    tiny = model.SHAPES["tiny"]
    one_b = model.SHAPES["1b"]
    seven_b = model.SHAPES["7b"]
    full2 = fabric.full(2)
    full4 = fabric.full(4)
    ring8 = fabric.ring(8)

    # ---- the frozen shape --------------------------------------------------

    assert [field.name for field in dataclasses.fields(s.Bucket)] == [
        "index", "tensors", "offset", "length", "padded", "group", "plan"], (
        "Bucket's fields are %r, not the frozen (index, tensors, offset, length, "
        "padded, group, plan)"
        % ([field.name for field in dataclasses.fields(s.Bucket)],))
    probe = s.Bucket(0, ("embed",), 0, 4, 4, ("r0",), fabric.Plan(transfers=()))
    assert (probe.index, probe.tensors, probe.offset, probe.length) == (
        0, ("embed",), 0, 4), (
        "a Bucket's fields read %r, not the frozen values" % (probe,))
    try:
        probe.length = 5
    except dataclasses.FrozenInstanceError:
        pass
    else:
        raise AssertionError(
            "a Bucket is mutable: a bucket is frozen data, but probe.length took "
            "the value 5")

    rows = _backward_rows(tiny)
    names = tuple(name for name, _, _ in rows)
    assert names[0] == "norm" and names[-1] == "embed", (
        "the backward layout starts at %r and ends at %r, not at the last "
        "tensor and the embedding" % (names[0], names[-1]))

    # ---- the schedule: the backward's order, one bucket that fits ----------

    for world in (full2, full4, ring8):
        bundles = s.bucket_schedule(tiny, world, bucket_bytes=BUCKET)
        assert isinstance(bundles, tuple), (
            "bucket_schedule answered %s, not a tuple of buckets: the schedule "
            "is data" % (type(bundles).__name__,))
        assert len(bundles) == 1, (
            "tiny's %d-element gradient at a 25 MB bucket makes %d buckets, not "
            "the one it fits in" % (tiny.params(), len(bundles)))
        bucket = bundles[0]
        assert (bucket.index, bucket.offset, bucket.length) == (0, 0, tiny.params()), (
            "tiny's one bucket is (index=%r, offset=%r, length=%r), not (0, 0, "
            "%d): the buckets tile the flat gradient in order"
            % (bucket.index, bucket.offset, bucket.length, tiny.params()))
        assert bucket.tensors == names, (
            "the bucket's tensors are %r, not the trainable tensors in the order "
            "the backward fills them (%r): a forward order starts the "
            "embedding's all-reduce first" % (bucket.tensors, names))
        assert tuple(bucket.group) == tuple(world.ranks), (
            "the bucket all-reduces over %r, not the world's own ranks %r"
            % (bucket.group, tuple(world.ranks)))
        want_padded = model.ceil_div(tiny.params(), len(world.ranks)) * len(world.ranks)
        assert bucket.padded == want_padded, (
            "the bucket carries %r elements over %d ranks, not the group's "
            "multiple %d the ring's equal chunks need"
            % (bucket.padded, len(world.ranks), want_padded))
        problems = fabric.legality_problems(world, bucket.plan)
        assert problems == (), (
            "the bucket's plan is not legal on %s: %r" % (world, problems))

    # ---- the 1B fixture: the bucket count and the tiling -------------------

    grads = one_b.params() * fabric.ELEMENT_BYTES
    want_count = model.ceil_div(grads, BUCKET)
    bundles = s.bucket_schedule(one_b, ring8, bucket_bytes=BUCKET)
    assert want_count == 175, (
        "the fixture changed: %d gradient bytes at %d make %d buckets"
        % (grads, BUCKET, want_count))
    assert len(bundles) == want_count, (
        "a 1B model's %d-element gradient at a %d-byte bucket makes %r buckets, "
        "not %d: the element is ELEMENT_BYTES (4) big — at PARAM_BYTES (2) it "
        "would be %d, and as one bucket it is 1"
        % (one_b.params(), BUCKET, len(bundles), want_count,
           model.ceil_div(one_b.params() * model.PARAM_BYTES, BUCKET)))
    capacity = BUCKET // fabric.ELEMENT_BYTES
    assert [bucket.index for bucket in bundles] == list(range(len(bundles))), (
        "the buckets' indices are %r, not 0..%d in order"
        % ([bucket.index for bucket in bundles], len(bundles) - 1))
    offset = 0
    for bucket in bundles:
        assert bucket.offset == offset, (
            "bucket %d starts at %r, not at %d: the buckets tile the flat "
            "gradient with no gap and no overlap"
            % (bucket.index, bucket.offset, offset))
        assert 0 < bucket.length <= capacity, (
            "bucket %d holds %r of the %d elements a bucket takes"
            % (bucket.index, bucket.length, capacity))
        assert bucket.length == min(capacity, one_b.params() - offset), (
            "bucket %d holds %r elements, not the %d left in the gradient (the "
            "last bucket is the remainder, not a whole bucket)"
            % (bucket.index, bucket.length, one_b.params() - offset))
        assert bucket.length <= bucket.padded < bucket.length + len(bucket.group), (
            "bucket %d's padded length %r is not the %r-element slice rounded up "
            "to the group's %d ranks"
            % (bucket.index, bucket.padded, bucket.length, len(bucket.group)))
        assert bucket.padded % len(bucket.group) == 0, (
            "bucket %d's padded length %r is not a multiple of the group's %d "
            "ranks: the ring's chunks are equal"
            % (bucket.index, bucket.padded, len(bucket.group)))
        offset += bucket.length
    assert offset == one_b.params(), (
        "the buckets cover %d elements, not the 1B model's %d"
        % (offset, one_b.params()))
    one_b_names = tuple(name for name, _, _ in _backward_rows(one_b))
    assert bundles[0].tensors[0] == one_b_names[0], (
        "the first bucket starts at %r, not at the last tensor %r the backward "
        "fills first" % (bundles[0].tensors[0], one_b_names[0]))
    assert bundles[-1].tensors[-1] == one_b_names[-1], (
        "the last bucket ends at %r, not at the embedding %r the backward fills "
        "last" % (bundles[-1].tensors[-1], one_b_names[-1]))
    covered = [name for bucket in bundles for name in bucket.tensors]
    assert set(covered) == set(one_b_names), (
        "the buckets name %r, not every trainable tensor of the 1B model"
        % (sorted(set(covered) ^ set(one_b_names)),))
    for edge in (bundles[0], bundles[-1]):
        under = tuple(
            name for name, start, elements in _backward_rows(one_b)
            if start < edge.offset + edge.length
            and edge.offset < start + elements)
        assert edge.tensors == under, (
            "bucket %d names %r, not the tensors its %d..%d slice really holds "
            "(%r): a bucket's tensors are the ones its own element range "
            "overlaps, in the backward's order"
            % (edge.index, edge.tensors, edge.offset, edge.offset + edge.length,
               under))
    assert seven_b.params() > one_b.params(), "the fixtures changed"

    # ---- the collectives: one per bucket, in order, the ring --------------

    batch, seq = 2, 4
    plan2 = s.data_parallel(tiny, full2, batch=batch, seq=seq)
    big = s.data_parallel(one_b, ring8, batch=batch, seq=seq)
    assert isinstance(plan2, s1.StepPlan), (
        "data_parallel answered %s, not a step plan" % (type(plan2).__name__,))
    assert [field.name for field in dataclasses.fields(s1.StepPlan)] == [
        "collectives", "compute", "memory"], "stage 1's StepPlan changed"
    bundles2 = s.bucket_schedule(tiny, full2, bucket_bytes=BUCKET)
    assert plan2.collectives == tuple(
        s1.Collective("dp", "grads", bucket.group, _per_rank(bucket.plan),
                      "ring", bucket.plan)
        for bucket in bundles2), (
        "the step's collectives are %r, not one `dp`/`grads`/`ring` collective "
        "per bucket in the backward's order, each sized by its own plan's "
        "per-rank elements" % (plan2.collectives,))
    for collective in plan2.collectives:
        assert (collective.axis, collective.name, collective.algo) == (
            "dp", "grads", "ring"), (
            "a bucket's collective is (axis=%r, name=%r, algo=%r), not the data "
            "parallel gradient all-reduce ('dp', 'grads', 'ring')"
            % (collective.axis, collective.name, collective.algo))
        assert collective.group == tuple(full2.ranks), (
            "the collective runs over %r, not the data-parallel ranks %r"
            % (collective.group, tuple(full2.ranks)))
        assert collective.length == _per_rank(collective.plan), (
            "the collective declares %r elements per rank, but its own plan "
            "moves %r: the declaration is the elements one rank moves"
            % (collective.length, _per_rank(collective.plan)))
    plan4 = s.data_parallel(tiny, full4, batch=batch, seq=seq)
    plan8 = s.data_parallel(tiny, ring8, batch=batch, seq=seq)
    for world, plan in ((full2, plan2), (full4, plan4), (ring8, plan8)):
        steps = len(world.ranks) - 1
        assert all(len(collective.plan.steps()) == 2 * steps
                   for collective in plan.collectives), (
            "a bucket's plan takes %r steps over %s, not the ring's 2(N-1) = %d: "
            "the whole buffer per step (chunk=None) and a chunk count the ring "
            "cannot pipeline are both the mistake this stage exists to show"
            % ([len(collective.plan.steps()) for collective in plan.collectives],
               world, 2 * steps))

    # ---- the bytes: the per-rank figure, times the group ------------------

    assert s1.plan_bytes(plan2) == 2 * (4 * tiny.params()) * 1 // 2, (
        "the two-rank step moves %r bytes per rank, not 2S(N-1)/N = %d (S here "
        "is the gradient's %d bytes): 2S per rank is the tree's "
        "reduce-and-broadcast, not the ring"
        % (s1.plan_bytes(plan2), 2 * (4 * tiny.params()) // 2, 4 * tiny.params()))
    assert s1.plan_bytes(plan4) == 2 * (4 * tiny.params()) * 3 // 4, (
        "the four-rank step moves %r bytes per rank, not 2S(N-1)/N = %d"
        % (s1.plan_bytes(plan4), 2 * (4 * tiny.params()) * 3 // 4))
    assert s1.plan_bytes(plan4) < 2 * 4 * tiny.params(), (
        "the four-rank step moves %r bytes per rank, not less than the "
        "gradient's own 2S = %d: a ring is not a broadcast"
        % (s1.plan_bytes(plan4), 2 * 4 * tiny.params()))
    padded8 = s.bucket_schedule(tiny, ring8, bucket_bytes=BUCKET)[0].padded
    assert s1.plan_bytes(plan8) == 4 * 2 * (padded8 - padded8 // 8), (
        "the eight-rank step moves %r bytes per rank, not the %r the padded "
        "%r-element bucket's ring moves"
        % (s1.plan_bytes(plan8), 4 * 2 * (padded8 - padded8 // 8), padded8))
    big = s.data_parallel(one_b, ring8, batch=batch, seq=seq)
    assert s1.plan_bytes(big) == 2 * (4 * one_b.params()) * 7 // 8, (
        "the 1B step moves %r bytes per rank, not 2S(N-1)/N = %d: the ring "
        "moves (N-1)/N of the buffer twice, not the whole buffer twice"
        % (s1.plan_bytes(big), 2 * (4 * one_b.params()) * 7 // 8))
    for world, plan in ((full2, plan2), (full4, plan4), (ring8, plan8)):
        assert s1.network_bytes(plan) == s1.plan_bytes(plan) * len(world.ranks), (
            "the network carries %r bytes, not the per-rank %r times the group's "
            "%d ranks: every member handles its own copy"
            % (s1.network_bytes(plan), s1.plan_bytes(plan), len(world.ranks)))

    # ---- the step's compute, and the comms hidden behind it ---------------

    want_compute = model.ComputeModel(flops_per_tick=FLOPS_PER_TICK).compute_ticks(
        tiny, batch=batch, seq=seq)
    assert plan2.compute == want_compute, (
        "the step's compute is %r, not the whole step's %r: the buckets' comms "
        "are not part of the compute"
        % (plan2.compute, want_compute))
    assert plan2.compute > 0, (
        "the step's compute is %r, not the step's own arithmetic"
        % (plan2.compute,))
    big_batch = 64
    big_ticks = model.ComputeModel(flops_per_tick=FLOPS_PER_TICK).compute_ticks(
        one_b, batch=big_batch, seq=8)
    big8 = s.data_parallel(one_b, ring8, batch=big_batch, seq=8)
    whole_batch = model.ComputeModel(flops_per_tick=FLOPS_PER_TICK).compute_ticks(
        one_b, batch=big_batch * len(ring8.ranks), seq=8)
    one_seq = model.ComputeModel(flops_per_tick=FLOPS_PER_TICK).compute_ticks(
        one_b, batch=1, seq=8)
    assert len({big_ticks, whole_batch, one_seq}) == 3, (
        "the compute fixture is degenerate: the rank's micro-batch, the whole "
        "step's batch and one sequence cost %r, %r and %r ticks"
        % (big_ticks, whole_batch, one_seq))
    assert big8.compute == big_ticks, (
        "the 1B step's compute is %r, not the %r of its own batch over each "
        "rank's micro-batch: the whole step's batch (%r) or one sequence (%r) is "
        "a different arithmetic"
        % (big8.compute, big_ticks, whole_batch, one_seq))
    for world in (full4, ring8):
        other = s.data_parallel(tiny, world, batch=batch, seq=seq)
        assert other.compute == plan2.compute, (
            "the step's compute changes with the world (%r over %d ranks, %r "
            "over %d): the compute is the step's, not the layout's"
            % (other.compute, len(world.ranks), plan2.compute, len(full2.ranks)))
    small = s.data_parallel(tiny, full2, batch=batch, seq=seq, bucket_bytes=1_000_000)
    assert small.compute == plan2.compute, (
        "the step's compute changes with the bucket size (%r at a 1 MB bucket, "
        "%r at 25 MB): the compute is the step's, not the schedule's"
        % (small.compute, plan2.compute))
    for world, plan in ((full2, plan2), (full4, plan4), (ring8, plan8)):
        comms = sum(s1.plan_ticks(world, collective.plan)
                    for collective in plan.collectives)
        assert s1.step_ticks(world, plan) == max(plan.compute, comms), (
            "the step costs %r ticks, not the maximum of %r compute and %r "
            "comms: the all-reduce hides behind the compute, it is not added to "
            "it" % (s1.step_ticks(world, plan), plan.compute, comms))

    # ---- the ledger: the whole state on every rank ------------------------

    want_lines = (
        s1.MemoryLine("params", tuple(full2.ranks), tiny.params() * model.PARAM_BYTES),
        s1.MemoryLine("gradients", tuple(full2.ranks), tiny.params() * model.PARAM_BYTES),
        s1.MemoryLine("masters", tuple(full2.ranks), tiny.params() * model.MASTER_BYTES),
        s1.MemoryLine("optimizer", tuple(full2.ranks), tiny.params() * model.OPTIMIZER_BYTES),
    )
    assert plan2.memory == want_lines, (
        "the ledger is %r, not %r: data parallel replicates the whole state — 16 "
        "bytes per parameter on every rank, divided over nothing (the divided "
        "ledger is ZeRO's rule, stages 3 and 4)"
        % (plan2.memory, want_lines))
    assert sum(line.bytes for line in plan2.memory) == 16 * tiny.params(), (
        "the ledger totals %r bytes per rank, not 16 per parameter"
        % (sum(line.bytes for line in plan2.memory),))
    assert [line.bytes for line in plan4.memory] == [
        line.bytes for line in plan2.memory], (
        "the ledger shrinks with the world (%r over four ranks, %r over two): "
        "data parallel shards nothing"
        % ([line.bytes for line in plan4.memory],
           [line.bytes for line in plan2.memory]))

    # ---- one rank: nothing to reduce, nothing to pay ----------------------

    one = fabric.full(1)
    assert s.bucket_schedule(tiny, one, bucket_bytes=BUCKET) == (), (
        "a one-rank schedule is %r, not empty: a group of one has nothing to "
        "reduce" % (s.bucket_schedule(tiny, one, bucket_bytes=BUCKET),))
    plan1 = s.data_parallel(tiny, one, batch=batch, seq=seq)
    assert plan1.collectives == (), (
        "the one-rank step issues %r collectives, not none"
        % (plan1.collectives,))
    assert s1.plan_bytes(plan1) == 0 and s1.network_bytes(plan1) == 0, (
        "the one-rank step moves %r bytes per rank and %r on the network, not 0"
        % (s1.plan_bytes(plan1), s1.network_bytes(plan1)))
    assert s1.step_ticks(one, plan1) == plan1.compute, (
        "the one-rank step costs %r ticks, not just its %r compute"
        % (s1.step_ticks(one, plan1), plan1.compute))
    assert plan1.compute == plan2.compute, (
        "the one-rank step's compute is %r and the two-rank step's %r: data "
        "parallel does not change the step's arithmetic"
        % (plan1.compute, plan2.compute))

    # ---- the refusals ------------------------------------------------------

    message = _refuses(model.ModelError, "a zero-byte bucket",
                       lambda: s.bucket_schedule(tiny, full2, bucket_bytes=0))
    assert "bucket_bytes" in message, (
        "the refusal of a zero-byte bucket does not name bucket_bytes: %r"
        % (message,))
    message = _refuses(model.ModelError, "a bool bucket size",
                       lambda: s.bucket_schedule(tiny, full2, bucket_bytes=True))
    assert "bucket_bytes" in message, (
        "the refusal of a bool bucket size does not name bucket_bytes: %r"
        % (message,))
    message = _refuses(model.ModelError, "a string bucket size",
                       lambda: s.bucket_schedule(tiny, full2, bucket_bytes="25 MB"))
    assert "bucket_bytes" in message, (
        "the refusal of a string bucket size does not name bucket_bytes: %r"
        % (message,))
    message = _refuses(model.ModelError, "a bucket below one element",
                       lambda: s.bucket_schedule(tiny, full2, bucket_bytes=3))
    assert "bucket_bytes" in message, (
        "the refusal of a bucket below one element does not name bucket_bytes: "
        "%r" % (message,))
    message = _refuses(model.ModelError, "a shape that is not a ModelShape",
                       lambda: s.bucket_schedule(("tiny",), full2, bucket_bytes=BUCKET))
    assert "shape" in message, (
        "the refusal of a shape that is not a ModelShape does not name shape: %r"
        % (message,))
    message = _refuses(model.ModelError, "a batch below one",
                       lambda: s.data_parallel(tiny, full2, batch=0, seq=seq))
    assert "batch" in message, (
        "the refusal of a batch below one does not name batch: %r" % (message,))

    # ---- the semantics: the reduction lands on the reference --------------

    for world in (full2, full4, ring8):
        size = len(world.ranks)
        want, first = _semantics(tiny, world, batch=1, seq=3)
        assert want != first, (
            "the two-rank fixture is vacuous: the whole step's %d-sequence "
            "gradient equals one rank's share" % (size * 1))
    want, first = _semantics(tiny, full4, batch=3, seq=2)
    assert want != first, (
        "the fixture is vacuous: the whole step's %d-sequence gradient equals "
        "one rank's share" % (4 * 3,))
    assert model.reference_gradients(one_b, batch=2, seq=1) != \
        model.reference_gradients(one_b, batch=1, seq=1), (
        "the 1B reference is flat in batch: the fixture proves nothing")

    # ---- deterministic -----------------------------------------------------

    assert s.bucket_schedule(tiny, ring8, bucket_bytes=BUCKET) == \
        s.bucket_schedule(tiny, ring8, bucket_bytes=BUCKET), (
        "two calls to bucket_schedule answered different schedules")
    assert s.data_parallel(tiny, full4, batch=2, seq=4) == \
        s.data_parallel(tiny, full4, batch=2, seq=4), (
        "two calls to data_parallel answered different plans")

    print("check_02: the data-parallel gradient is bucketed in the backward's "
          "order, each bucket is the pipelined ring whose declaration is its own "
          "per-rank movement, plan_bytes is 2S(N-1)/N per rank and network_bytes "
          "is per-rank times the group, the step's compute is the whole step's "
          "with the comms hidden behind it, the ledger is the replicated state, "
          "and the all-reduce of the ranks' shares lands on the reference")

# --- stage 3 -----------------------------------------------------------------------
def check_3():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("H1_REPO"), start, os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "distributed-training-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set H1_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call):
        """The message of the refusal `call` must raise, or the mistake named.

        A return, or any other exception, is the mistake `what` names — except a
        `NotImplementedError`, which escapes: an untouched template must surface as
        the `TODO` it is, never as an assertion about a plan that does not exist.
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

    def _moved_per_rank(fabric_plan, group):
        """The elements one rank of `fabric_plan` sends: the maximum over `group`.

        Read off the plan's own transfers — the declared `Collective.length` has to
        be this, not the whole buffer and not the network's share.
        """
        sent = {}
        for transfer in fabric_plan.transfers:
            sent[transfer.src] = sent.get(transfer.src, 0) + transfer.length
        return max(sent.get(rank, 0) for rank in group)

    import fabric
    import model
    import plans
    import stage_01

    import stage_03 as s

    # ---- shard_partition: the remainder one byte at a time ----------------

    assert s.shard_partition(100, 4) == (25, 25, 25, 25), (
        "100 bytes over four ranks are %r, not four equal 25s: a state that "
        "divides the world is cut exactly" % (s.shard_partition(100, 4),))
    assert s.shard_partition(3104, 3) == (1035, 1035, 1034), (
        "3104 bytes over three ranks are %r, not (1035, 1035, 1034): the two "
        "bytes of remainder are spread one at a time over the first ranks, "
        "never dropped" % (s.shard_partition(3104, 3),))
    assert s.shard_partition(3104, 5) == (621, 621, 621, 621, 620), (
        "3104 bytes over five ranks are %r, not (621, 621, 621, 621, 620): "
        "four ranks hold one byte more than the last" % (s.shard_partition(3104, 5),))
    assert s.shard_partition(1, 4) == (1, 0, 0, 0), (
        "one byte over four ranks is %r, not (1, 0, 0, 0): the remainder goes "
        "to the first rank and a rank the state does not reach is empty"
        % (s.shard_partition(1, 4),))
    assert s.shard_partition(3, 8) == (1, 1, 1, 0, 0, 0, 0, 0), (
        "three bytes over eight ranks are %r, not the three on the first ranks: "
        "the extra goes to the first ranks, not the last, and is spread one "
        "byte at a time" % (s.shard_partition(3, 8),))
    assert s.shard_partition(0, 4) == (0, 0, 0, 0), (
        "an empty state over four ranks is %r, not four empty shards"
        % (s.shard_partition(0, 4),))
    assert s.shard_partition(388, 1) == (388,), (
        "388 bytes over one rank are %r, not the whole state"
        % (s.shard_partition(388, 1),))

    # A parameter tensor whose element count does not divide the world: the
    # tiny fixture's embedding, 48 parameters at 2 bytes each, over five ranks.
    tiny = model.SHAPES["tiny"]
    assert tiny.params() == 388, "the fixture changed: tiny has %d params" % (tiny.params(),)
    embedding = tiny.tensors()[0]
    assert embedding.name == "embed" and embedding.elements == 48, (
        "the fixture changed: the first tensor is %r" % (embedding,))
    assert s.shard_partition(model.PARAM_BYTES * embedding.elements, 5) == (
        20, 19, 19, 19, 19), (
        "the 96 bytes of the embedding (48 parameters, 2 bytes each) over five "
        "ranks are %r, not (20, 19, 19, 19, 19): 48 does not divide 5, and the "
        "one byte of remainder is the first rank's"
        % (s.shard_partition(model.PARAM_BYTES * embedding.elements, 5),))

    for total in (0, 1, 7, 388, 3104, 6208, 876_513_792):
        for ranks in (1, 2, 3, 5, 8, 64):
            shards = s.shard_partition(total, ranks)
            assert isinstance(shards, tuple) and len(shards) == ranks, (
                "%d bytes over %d ranks are %r, not a tuple of %d shares"
                % (total, ranks, shards, ranks))
            assert sum(shards) == total, (
                "the shards %r of %d bytes over %d ranks sum to %r, not %d: a "
                "partition that divides the world and drops the state loses "
                "the remainder" % (shards, total, ranks, sum(shards), total))
            assert max(shards) - min(shards) <= 1, (
                "the shards %r of %d bytes over %d ranks differ by more than "
                "one: the remainder is spread one byte at a time"
                % (shards, total, ranks))
            assert shards[0] == model.ceil_div(total, ranks), (
                "the first of %r is %r, not %d: the first rank holds the "
                "largest shard — the one the ledger reports"
                % (shards, shards[0], model.ceil_div(total, ranks)))
            assert shards[-1] == total // ranks, (
                "the last of %r is %r, not %d: no rank holds less than the "
                "floor, and the extra went to the first ranks"
                % (shards, shards[-1], total // ranks))

    for tensor in tiny.tensors():
        state = model.PARAM_BYTES * tensor.elements
        for ranks in (2, 3, 5, 8):
            shards = s.shard_partition(state, ranks)
            assert sum(shards) == state, (
                "the shards %r of %r's %d-byte state over %d ranks sum to %r, "
                "not %d: a shard count that divides the world but not the state "
                "still has to hold every byte"
                % (shards, tensor.name, state, ranks, sum(shards), state))

    message = _refuses(model.ModelError, "a rank count below one",
                       lambda: s.shard_partition(100, 0))
    assert "ranks" in message, (
        "the refusal of a rank count below one does not name ranks: %r" % (message,))
    message = _refuses(model.ModelError, "a bool rank count",
                       lambda: s.shard_partition(100, True))
    assert "ranks" in message, (
        "the refusal of a bool rank count does not name ranks: %r" % (message,))
    message = _refuses(model.ModelError, "a negative byte count",
                       lambda: s.shard_partition(-1, 4))
    assert "total_bytes" in message or "-1" in message, (
        "the refusal of a negative state does not name the bytes: %r" % (message,))
    message = _refuses(model.ModelError, "a non-int byte count",
                       lambda: s.shard_partition("3104", 4))
    assert "total_bytes" in message or "3104" in message, (
        "the refusal of a non-int state does not name the bytes: %r" % (message,))
    assert s.shard_partition(3104, 3) == s.shard_partition(3104, 3), (
        "two calls of shard_partition(3104, 3) disagree: a partition is a "
        "function of its arguments")

    # ---- assemble: the state the shards add up to, exactly ----------------

    assert s.assemble((1, 1, 1)) == 3, (
        "the shards (1, 1, 1) reassemble to %r, not 3: the state is their sum"
        % (s.assemble((1, 1, 1)),))
    assert s.assemble((0,)) == 0, (
        "the shard (0,) reassembles to %r, not nothing" % (s.assemble((0,)),))

    for tensor in tiny.tensors():
        state = model.PARAM_BYTES * tensor.elements
        for ranks in (1, 2, 3, 5, 8):
            shards = s.shard_partition(state, ranks)
            assert s.assemble(shards) == state, (
                "the %d-byte state of %r reassembles from %r to %r, not %d: the "
                "reassembled state is the whole state, however it was cut"
                % (state, tensor.name, shards, s.assemble(shards), state))

    seven_b = model.SHAPES["7b"]
    whole_state = 16 * seven_b.params()
    for ranks in (1, 3, 5, 8):
        shards = s.shard_partition(whole_state, ranks)
        assert s.assemble(shards) == whole_state, (
            "the reference 16-bytes-per-parameter state of 7b (%d bytes) "
            "reassembles from %d ranks to %r, not %d"
            % (whole_state, ranks, s.assemble(shards), whole_state))

    message = _refuses(model.ModelError, "a negative shard",
                       lambda: s.assemble((2, -1)))
    assert "shard" in message or "-1" in message, (
        "the refusal of a negative shard does not name it: %r" % (message,))
    message = _refuses(model.ModelError, "a non-int shard",
                       lambda: s.assemble((2, "1")))
    assert "shard" in message or "1" in message, (
        "the refusal of a non-int shard does not name it: %r" % (message,))
    message = _refuses(model.ModelError, "a list of shards",
                       lambda: s.assemble([2, 1]))
    assert "shards" in message, (
        "the refusal of a list of shards does not name the partition: %r"
        % (message,))
    message = _refuses(model.ModelError, "an empty partition",
                       lambda: s.assemble(()))
    assert "shards" in message, (
        "the refusal of an empty partition does not name it: %r" % (message,))

    # ---- zero: the 7B fixture the contract names, on full(8) --------------

    eight = fabric.full(8)
    params = seven_b.params()
    assert params == 7_012_110_336, "the fixture changed: 7b has %d params" % (params,)

    z1 = s.zero(seven_b, eight, stage=1)
    z2 = s.zero(seven_b, eight, stage=2)
    assert isinstance(z1, stage_01.StepPlan) and isinstance(z2, stage_01.StepPlan), (
        "zero returned %r / %r, not the StepPlan stage 1 froze"
        % (type(z1).__name__, type(z2).__name__))
    assert z1.compute == 0 and z2.compute == 0, (
        "a ZeRO step claims %r / %r ticks of compute: this stage has no batch "
        "and no sequence, so it prices the state and owns no compute"
        % (z1.compute, z2.compute))

    want1 = (
        stage_01.MemoryLine("params", eight.ranks, 2 * params),
        stage_01.MemoryLine("gradients", eight.ranks, 2 * params),
        stage_01.MemoryLine("masters", eight.ranks, model.ceil_div(4 * params, 8)),
        stage_01.MemoryLine("optimizer", eight.ranks, model.ceil_div(8 * params, 8)),
    )
    assert z1.memory == want1, (
        "ZeRO-1's ledger is %r, not %r: the parameters and their gradients are "
        "replicated whole and only the 12 bytes of optimizer state (the fp32 "
        "masters with the two moments) are divided over the group"
        % (z1.memory, want1))
    want2 = (
        stage_01.MemoryLine("params", eight.ranks, 2 * params),
        stage_01.MemoryLine("gradients", eight.ranks, model.ceil_div(2 * params, 8)),
        stage_01.MemoryLine("masters", eight.ranks, model.ceil_div(4 * params, 8)),
        stage_01.MemoryLine("optimizer", eight.ranks, model.ceil_div(8 * params, 8)),
    )
    assert z2.memory == want2, (
        "ZeRO-2's ledger is %r, not %r: ZeRO-2 divides the gradients as well, "
        "and never the other way round" % (z2.memory, want2))

    assert z1.memory[0].bytes == 2 * params and z2.memory[0].bytes == 2 * params, (
        "the parameters are reported as %r and %r bytes per rank, not 2 per "
        "parameter held whole in both stages: dividing the parameters is ZeRO-3 "
        "(stage 4), not this one" % (z1.memory[0].bytes, z2.memory[0].bytes))
    assert z1.memory[1].bytes == 2 * params, (
        "ZeRO-1 reports %r bytes of gradient per rank, not the whole 2 per "
        "parameter: sharding the gradients is ZeRO-2" % (z1.memory[1].bytes,))
    assert z2.memory[1].bytes == model.ceil_div(2 * params, 8), (
        "ZeRO-2 reports %r bytes of gradient per rank, not the eighth of the "
        "group: ZeRO-2's saving is exactly the gradient shard"
        % (z2.memory[1].bytes,))
    assert [line.bytes for line in z1.memory] == [
        14_024_220_672, 14_024_220_672, 3_506_055_168, 7_012_110_336], (
        "the 7B/full(8) ZeRO-1 ledger is %r, not the recomputed "
        "(2P, 2P, 4P/8, 8P/8)"
        % ([line.bytes for line in z1.memory],))
    assert [line.bytes for line in z2.memory] == [
        14_024_220_672, 1_753_027_584, 3_506_055_168, 7_012_110_336], (
        "the 7B/full(8) ZeRO-2 ledger is %r, not the recomputed "
        "(2P, 2P/8, 4P/8, 8P/8)"
        % ([line.bytes for line in z2.memory],))

    total1 = sum(line.bytes for line in z1.memory)
    total2 = sum(line.bytes for line in z2.memory)
    assert total1 == 38_566_606_848 and total2 == 26_295_413_760, (
        "the two ledgers total %r and %r bytes per rank, not 7B/full(8)'s "
        "5.5 P and 3.75 P" % (total1, total2))
    assert 8 * total1 == (4 * 8 + 12) * params, (
        "ZeRO-1's per-rank total is %r: with the group at 8 it must be "
        "`4 + 12/8` bytes per parameter, 4 P + 12 P / 8" % (total1,))
    assert 8 * total2 == (2 * 8 + 14) * params, (
        "ZeRO-2's per-rank total is %r: with the group at 8 it must be "
        "`2 + 2/8 + 12/8` bytes per parameter, 2 P + 14 P / 8" % (total2,))
    assert total2 < total1, (
        "ZeRO-2 holds %r bytes per rank, ZeRO-1 %r: the ladder only runs down — "
        "a stage that shards the gradients cannot hold more state than the one "
        "that does not" % (total2, total1))
    assert total1 - total2 == 2 * params - model.ceil_div(2 * params, 8), (
        "ZeRO-2 saves %r bytes per rank over ZeRO-1, not the whole gradient "
        "minus its shard" % (total1 - total2,))

    # ---- zero: the collectives, and what the plan's own transfers move ----

    assert len(z1.collectives) == 1, (
        "a stage=1 plan issues %d collectives, not one gradient all-reduce"
        % (len(z1.collectives),))
    assert len(z2.collectives) == 2, (
        "a stage=2 plan issues %d collectives, not stage 1's one plus the "
        "parameter all-gather the sharded gradient forces"
        % (len(z2.collectives),))

    grads1 = z1.collectives[0]
    assert (grads1.axis, grads1.name, grads1.group, grads1.algo) == (
        "dp", "grads", eight.ranks, "ring"), (
        "ZeRO-1's collective is %r, not a `dp` `grads` collective over the "
        "group run as a ring all-reduce — a reduce-scatter here is ZeRO-2's "
        "gradient" % ((grads1.axis, grads1.name, grads1.group, grads1.algo),))
    grads2, params2 = z2.collectives
    assert (grads2.axis, grads2.name, grads2.group, grads2.algo) == (
        "dp", "grads", eight.ranks, "gather-scatter"), (
        "ZeRO-2's gradient collective is %r, not a reduce-scatter over the "
        "group" % ((grads2.axis, grads2.name, grads2.group, grads2.algo),))
    assert (params2.axis, params2.name, params2.group, params2.algo) == (
        "dp", "params", eight.ranks, "gather-scatter"), (
        "the extra collective is %r, not the parameter all-gather stage 2 "
        "issues because each rank only updated its own shard"
        % ((params2.axis, params2.name, params2.group, params2.algo),))

    words = model.ceil_div(params * model.PARAM_BYTES, fabric.ELEMENT_BYTES)
    per_rank = words * 7 // 8
    assert words == 3_506_055_168 and per_rank == 3_067_798_272, (
        "the 7B buffers are %r words and %r per rank over eight ranks, not the "
        "recomputed 2P/4 and its seven eighths" % (words, per_rank))
    assert grads1.length == 2 * per_rank, (
        "ZeRO-1's gradient all-reduce declares %r elements per rank, not "
        "2S(N-1)/N = %r: an all-reduce moves the buffer twice round the ring"
        % (grads1.length, 2 * per_rank))
    assert grads2.length == per_rank and params2.length == per_rank, (
        "ZeRO-2's collectives declare %r and %r elements per rank, not "
        "S(N-1)/N = %r each" % (grads2.length, params2.length, per_rank))

    for collective in z1.collectives + z2.collectives:
        moved = _moved_per_rank(collective.plan, collective.group)
        assert moved == collective.length, (
            "the %r collective declares %r elements per rank but its own "
            "transfers move %r: the length is what the plan moves per rank, "
            "not the whole buffer and not the network's share"
            % (collective.name, collective.length, moved))
        problems = fabric.legality_problems(eight, collective.plan)
        assert problems == (), (
            "the %r collective's plan is not legal on full(8): %r"
            % (collective.name, problems))

    bytes1 = stage_01.plan_bytes(z1)
    bytes2 = stage_01.plan_bytes(z2)
    assert bytes1 == fabric.ELEMENT_BYTES * 2 * per_rank, (
        "ZeRO-1 moves %r bytes per rank, not the recomputed "
        "2S(N-1)/N = 2 * 2P * (N-1)/N" % (bytes1,))
    assert bytes2 == bytes1, (
        "ZeRO-2 moves %r bytes per rank against ZeRO-1's %r: swapping the "
        "gradient all-reduce for a reduce-scatter plus the parameter all-gather "
        "changes what is resident, not what crosses the fabric"
        % (bytes2, bytes1))
    extra = fabric.ELEMENT_BYTES * params2.length
    assert extra == 2 * params * 7 // 8, (
        "the parameter all-gather moves %r bytes per rank, not 2P(N-1)/N" % (extra,))
    assert stage_01.step_ticks(eight, z2) == stage_01.step_ticks(eight, z1), (
        "ZeRO-2's step costs %r ticks against ZeRO-1's %r: the same bytes over "
        "the same number of ring steps overlap the same compute"
        % (stage_01.step_ticks(eight, z2), stage_01.step_ticks(eight, z1)))

    assert s.zero(seven_b, eight, stage=2) == z2, (
        "two calls of zero(7b, full(8), stage=2) return different steps: a plan "
        "is a function of its inputs")

    # ---- zero: a state that does not divide the world ---------------------

    odd = model.ModelShape(layers=1, hidden=5, heads=1, ffn_hidden=5, vocab=5)
    assert odd.params() == 215, (
        "the hand fixture changed: it has %d parameters" % (odd.params(),))
    three = fabric.full(3)
    odd1 = s.zero(odd, three, stage=1)
    odd2 = s.zero(odd, three, stage=2)
    assert [line.bytes for line in odd1.memory] == [
        430, 430, model.ceil_div(4 * 215, 3), model.ceil_div(8 * 215, 3)], (
        "the 215-parameter state over three ranks reads %r, not "
        "(2P, 2P, ceil(4P/3), ceil(8P/3)): a share that does not divide is "
        "ceiled, not floored" % ([line.bytes for line in odd1.memory],))
    assert [line.bytes for line in odd1.memory] == [430, 430, 287, 574], (
        "the 215-parameter ZeRO-1 ledger over three ranks is %r, not "
        "(430, 430, 287, 574)" % ([line.bytes for line in odd1.memory],))
    assert [line.bytes for line in odd2.memory] == [430, 144, 287, 574], (
        "the 215-parameter ZeRO-2 ledger over three ranks is %r, not "
        "(430, 144, 287, 574)" % ([line.bytes for line in odd2.memory],))
    assert odd1.memory[2].bytes == s.shard_partition(4 * 215, 3)[0], (
        "the ledger reports %r bytes of masters, not the first rank's exact "
        "share %r: the line is the partition's largest shard"
        % (odd1.memory[2].bytes, s.shard_partition(4 * 215, 3)[0]))
    assert odd1.memory[3].bytes == s.shard_partition(8 * 215, 3)[0], (
        "the ledger reports %r bytes of optimizer state, not the first rank's "
        "exact share %r" % (odd1.memory[3].bytes, s.shard_partition(8 * 215, 3)[0]))
    assert odd2.memory[1].bytes == s.shard_partition(2 * 215, 3)[0], (
        "the ZeRO-2 gradient line is %r bytes, not the first rank's exact "
        "share %r" % (odd2.memory[1].bytes, s.shard_partition(2 * 215, 3)[0]))
    for collective in odd1.collectives + odd2.collectives:
        assert fabric.legality_problems(three, collective.plan) == (), (
            "the %r collective of the 215-parameter fixture is not legal on "
            "full(3): %r" % (collective.name,
                             fabric.legality_problems(three, collective.plan)))

    # ---- the reassembly, on the fabric ------------------------------------

    tiny_two = fabric.full(2)
    tiny_words = model.ceil_div(tiny.params() * model.PARAM_BYTES,
                               fabric.ELEMENT_BYTES)
    assert tiny_words == 194 and tiny_words % 2 == 0, (
        "the tiny fixture's buffers are %r words over two ranks" % (tiny_words,))
    buffers = fabric.buffers(2, tiny_words)
    whole = fabric.reference(buffers)

    step1 = s.zero(tiny, tiny_two, stage=1)
    assert len(step1.collectives) == 1, (
        "the two-rank ZeRO-1 step issues %d collectives"
        % (len(step1.collectives),))
    result1 = fabric.run(tiny_two, step1.collectives[0].plan, buffers)
    for rank in tiny_two.ranks:
        assert result1[rank] == whole, (
            "after ZeRO-1's all-reduce rank %r holds %r, not the whole "
            "reference sum %r: the gradient must be the same on every rank"
            % (rank, result1[rank][:4], whole[:4]))

    step2 = s.zero(tiny, tiny_two, stage=2)
    shard = tiny_words // 2
    result2 = fabric.run(tiny_two, step2.collectives[0].plan, buffers)
    seen = result2[tiny_two.ranks[0]][:shard] + result2[tiny_two.ranks[1]][shard:]
    assert seen == whole, (
        "the ZeRO-2 gradient shards reassemble to %r, not the reference sum %r: "
        "shard c of the element-wise sum ends on rank c"
        % (seen[:4], whole[:4]))
    assert result2[tiny_two.ranks[0]][shard:] != whole[shard:], (
        "rank r0 holds the whole gradient after ZeRO-2's reduce-scatter: only "
        "its own shard is resident, which is the 2/N the stage bought")

    tagged = fabric.buffers(2, tiny_words,
                            fill=lambda index, j: (index + 1) * 100_000 + j)
    gathered = fabric.run(tiny_two, step2.collectives[1].plan, tagged)
    for rank in tiny_two.ranks:
        assert gathered[rank][:shard] == tagged[tiny_two.ranks[0]][:shard], (
            "rank %r does not hold r0's shard after the parameter all-gather: "
            "the parameters must be whole again for the next forward" % (rank,))
        assert gathered[rank][shard:] == tagged[tiny_two.ranks[1]][shard:], (
            "rank %r does not hold r1's shard after the parameter all-gather"
            % (rank,))

    # ---- the axis of one is the single-device reference -------------------

    one = fabric.full(1)
    sole1 = s.zero(tiny, one, stage=1)
    sole2 = s.zero(tiny, one, stage=2)
    assert sole1.collectives == () and sole2.collectives == (), (
        "an axis of one issues %r / %r collectives, not none: a group of one "
        "rank needs no plan and costs no comms"
        % (sole1.collectives, sole2.collectives))
    assert [line.bytes for line in sole2.memory] == [
        776, 776, 1552, 3104], (
        "the one-rank ledger is %r, not the reference 16 bytes per parameter "
        "held whole" % ([line.bytes for line in sole2.memory],))
    assert sum(line.bytes for line in sole1.memory) == 16 * tiny.params(), (
        "a one-rank ZeRO step holds %r bytes per rank, not the reference "
        "16 per parameter" % (sum(line.bytes for line in sole1.memory),))
    assert stage_01.plan_bytes(sole1) == 0 and stage_01.step_ticks(one, sole2) == 0, (
        "a one-rank ZeRO step costs %r bytes and %r ticks, not nothing"
        % (stage_01.plan_bytes(sole1), stage_01.step_ticks(one, sole2)))

    # ---- the group default, and the refusals ------------------------------

    assert s.zero(tiny, tiny_two, stage=1) == s.zero(
        tiny, tiny_two, stage=1, group=tiny_two.ranks), (
        "zero's default group is not the whole world")
    assert s.zero(tiny, tiny_two, stage=1).collectives[0].group == tiny_two.ranks, (
        "the default group is %r, not the world's own rank order"
        % (s.zero(tiny, tiny_two, stage=1).collectives[0].group,))

    message = _refuses(model.ModelError, "a stage outside (1, 2)",
                       lambda: s.zero(tiny, tiny_two, stage=3))
    assert "stage" in message, (
        "the refusal of stage=3 does not name the stage: %r" % (message,))
    _refuses(model.ModelError, "stage 0",
             lambda: s.zero(tiny, tiny_two, stage=0))
    _refuses(model.ModelError, "a bool stage",
             lambda: s.zero(tiny, tiny_two, stage=True))
    _refuses(model.ModelError, "a string stage",
             lambda: s.zero(tiny, tiny_two, stage="1"))
    message = _refuses(model.ModelError, "a shape that is not a ModelShape",
                       lambda: s.zero("7b", tiny_two, stage=1))
    assert "shape" in message, (
        "the refusal of a non-ModelShape does not name the shape: %r" % (message,))
    message = _refuses(fabric.FabricError, "a world that is not a fabric",
                       lambda: s.zero(tiny, None, stage=1))
    assert "world" in message or "None" in message, (
        "the refusal of a non-fabric world does not name it: %r" % (message,))
    message = _refuses(fabric.FabricError, "a group naming an unknown rank",
                       lambda: s.zero(tiny, tiny_two, stage=1, group=("r0", "r9")))
    assert "r9" in message, (
        "the refusal of an unknown rank does not name it: %r" % (message,))
    message = _refuses(fabric.FabricError, "a group the topology cannot serve",
                       lambda: s.zero(tiny, fabric.ring(8), stage=1,
                                      group=("r0", "r4")))
    assert "r0" in message and "r4" in message, (
        "the refusal of an unroutable group does not name its members: %r"
        % (message,))
    message = _refuses(fabric.FabricError, "a buffer the group does not divide",
                       lambda: s.zero(tiny, fabric.full(3), stage=2))
    assert "194" in message or "chunk" in message or "multiple" in message, (
        "the refusal of a buffer the three-rank group cannot chunk does not "
        "name the length: %r" % (message,))

    print("check_03: ZeRO-1 shards the 12 bytes of optimizer state over the "
          "group and ZeRO-2 the gradients as well (4 + 12/N then "
          "2 + 2/N + 12/N per parameter), shard_partition spreads the "
          "remainder one byte at a time over the first ranks so the shards "
          "reassemble to the reference state exactly, the ledger reports the "
          "largest shard per rank, and a stage=2 plan adds the parameter "
          "all-gather the sharded gradient forces")

# --- stage 4 -----------------------------------------------------------------------
def check_4():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("H1_REPO"), start, os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "distributed-training-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set H1_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call):
        """The message of the refusal `call` must raise, or the mistake named.

        A return, or any other exception, is the mistake `what` names — except a
        `NotImplementedError`, which escapes: an untouched template must surface as
        the `TODO` it is, never as an assertion about a plan that does not exist.
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

    def _moved_per_rank(fabric_plan, group):
        """The elements one rank of `fabric_plan` sends: the maximum over `group`.

        Read off the plan's own transfers — the declared `Collective.length` has to
        be this, not the whole buffer and not the network's share.
        """
        sent = {}
        for transfer in fabric_plan.transfers:
            sent[transfer.src] = sent.get(transfer.src, 0) + transfer.length
        return max(sent.get(rank, 0) for rank in group)

    def _plan_buffer_bytes(fabric_plan, element_bytes):
        """The whole buffer a fabric plan is issued over, in bytes.

        A ring collective keeps one chunk of its buffer at each offset it touches,
        so the buffer reaches as far as the farthest transfer does.
        """
        if not fabric_plan.transfers:
            return 0
        return element_bytes * max(transfer.offset + transfer.length
                                   for transfer in fabric_plan.transfers)

    def _words(tensors, unit, param_bytes, element_bytes):
        """The `ELEMENT_BYTES` words a unit's bf16 parameters occupy."""
        return -(-sum(tensors[index].elements for index in unit) * param_bytes
                 // element_bytes)

    def _module_of(name):
        """The module a tensor belongs to: `layer.7.ffn.w1` is `layer.7`."""
        parts = name.split(".")
        if parts[0] == "layer" and len(parts) > 1:
            return "layer." + parts[1]
        return parts[0]

    import fabric
    import model
    import stage_01
    import stage_03

    import stage_04 as s

    one_b = model.SHAPES["1b"]
    ring8 = fabric.ring(8)
    ranks = ring8.ranks
    total = len(ranks)
    tensors = one_b.tensors()
    params = one_b.params()
    element = fabric.ELEMENT_BYTES
    rate = model.PARAM_BYTES

    assert params == 1_093_224_448, "the fixture changed: 1b has %d params" % (params,)
    assert len(tensors) == 1 + 7 * one_b.layers + 1 == 142, (
        "the fixture changed: 1b has %d tensors" % (len(tensors),))
    assert tensors[0].name == "embed" and tensors[-1].name == "norm", (
        "the fixture changed: the first and last tensors are %r and %r"
        % (tensors[0].name, tensors[-1].name))
    layer_params = sum(tensor.elements for tensor in tensors[1:8])
    layer_bytes = rate * layer_params
    assert layer_params == 51_384_320 and layer_bytes == 102_768_640, (
        "the fixture changed: one layer is %r parameters, %r bytes at %d per "
        "parameter" % (layer_params, layer_bytes, rate))
    wrap = layer_bytes

    # ---- wrap_policy: the atoms, the budget, and who the budget governs ----

    units = s.wrap_policy(one_b, ring8, wrap_bytes=wrap)
    assert isinstance(units, tuple) and units, (
        "wrap_policy returned %r, not a non-empty tuple of units" % (units,))
    assert all(isinstance(unit, tuple) for unit in units), (
        "wrap_policy returned %r: a unit is a tuple of indices into "
        "shape.tensors()" % (units,))
    assert [index for unit in units for index in unit] == list(range(len(tensors))), (
        "the units %r do not cover every tensor once, in order: a policy is a "
        "partition of shape.tensors()" % (units,))
    assert len(units) == 2 + one_b.layers == 22, (
        "a one-layer budget makes %d units, not one per module — the "
        "embedding, the %d layers and the trailing norm" % (len(units), one_b.layers))
    for unit in units:
        modules = {_module_of(tensors[index].name) for index in unit}
        assert len(modules) == 1, (
            "the unit %r mixes the modules %r: a wrap unit never mixes two "
            "layers' parameters" % (unit, sorted(modules)))
    assert units[0] == (0,) and units[-1] == (len(tensors) - 1,), (
        "the first and last units are %r and %r, not the embedding alone and "
        "the norm alone" % (units[0], units[-1]))
    for layer in range(one_b.layers):
        want = tuple(range(1 + 7 * layer, 1 + 7 * layer + 7))
        assert units[1 + layer] == want, (
            "layer %d is wrapped as %r, not as its own seven tensors %r: a "
            "wrap unit never splits a layer and never merges two"
            % (layer, units[1 + layer], want))
    assert len(units[0]) == 1 and units[0][0] == 0, (
        "the embedding is wrapped with %r: it is a module of its own"
        % (units[0],))

    embed_bytes = rate * tensors[0].elements
    assert embed_bytes == 131_072_000 and embed_bytes > wrap, (
        "the fixture changed: the embedding is %r bytes against a %r-byte "
        "budget" % (embed_bytes, wrap))
    assert units[0] == (0,), (
        "the embedding is not a unit of its own at a one-layer budget: the "
        "budget governs the layers, and a module that cannot be cut is a unit "
        "however big it is")

    two_layers = 2 * layer_bytes
    merged = s.wrap_policy(one_b, ring8, wrap_bytes=two_layers)
    assert len(merged) == 1 + one_b.layers // 2 + 1 == 12, (
        "a two-layer budget makes %d units, not the embedding, ten pairs of "
        "layers and the norm" % (len(merged),))
    assert merged[0] == (0,) and merged[-1] == (len(tensors) - 1,), (
        "the merged policy's first and last units are %r and %r"
        % (merged[0], merged[-1]))
    assert merged[1] == tuple(range(1, 15)) and merged[2] == tuple(range(15, 29)), (
        "the first merged pair is %r and the second %r, not the two layers "
        "whose parameters fit the budget together" % (merged[1], merged[2]))
    assert len(merged[1]) == 14, (
        "a merged unit holds %d tensors, not two layers' fourteen"
        % (len(merged[1]),))

    whole = s.wrap_policy(one_b, ring8, wrap_bytes=2 * params)
    assert whole == (tuple(range(len(tensors))),), (
        "a budget that holds the model makes %r, not one unit of every tensor"
        % (whole,))
    assert s.wrap_policy(one_b, ring8, wrap_bytes=wrap) == units, (
        "two calls of wrap_policy(1b, ring(8)) disagree: a policy is a function "
        "of its inputs")

    message = _refuses(model.ModelError, "a budget below one layer",
                       lambda: s.wrap_policy(one_b, ring8, wrap_bytes=wrap - 1))
    assert "layer" in message, (
        "the refusal of a one-layer-minus-one budget does not name the layer "
        "that cannot fit: %r" % (message,))
    assert "102768640" in message or "51384320" in message, (
        "the refusal does not interpolate the layer's actual size: %r" % (message,))
    for bad in (0, -1, True, "102768640", None):
        message = _refuses(
            model.ModelError, "a wrap_bytes of %r" % (bad,),
            lambda bad=bad: s.wrap_policy(one_b, ring8, wrap_bytes=bad))
        assert "wrap_bytes" in message, (
            "the refusal of wrap_bytes=%r does not name it: %r" % (bad, message))
        assert "layer" not in message, (
            "the refusal of wrap_bytes=%r reads %r: a budget that is not a "
            "count is refused before the policy reaches a layer, so the message "
            "names the budget and never a layer" % (bad, message))
    message = _refuses(model.ModelError, "a shape that is not a ModelShape",
                       lambda: s.wrap_policy("1b", ring8, wrap_bytes=wrap))
    assert "shape" in message, (
        "the refusal of a non-ModelShape does not name the shape: %r" % (message,))
    message = _refuses(fabric.FabricError, "a world that is not a fabric",
                       lambda: s.wrap_policy(one_b, None, wrap_bytes=wrap))
    assert "world" in message or "None" in message, (
        "the refusal of a non-fabric world does not name it: %r" % (message,))

    # ---- fully_sharded: one pair of collectives per unit -------------------

    plan = s.fully_sharded(one_b, ring8, wrap_bytes=wrap)
    assert isinstance(plan, stage_01.StepPlan), (
        "fully_sharded returned %r, not the StepPlan stage 1 froze"
        % (type(plan).__name__,))
    assert plan.compute == 0, (
        "a fully sharded step claims %r ticks of compute: this stage prices the "
        "state and what crosses the fabric, not the arithmetic the gathered "
        "parameters enable" % (plan.compute,))
    assert len(plan.collectives) == 2 * len(units) == 44, (
        "the plan issues %d collectives, not one all-gather and one "
        "reduce-scatter for each of the %d units — the whole model is never "
        "gathered at once" % (len(plan.collectives), len(units)))
    assert [collective.name for collective in plan.collectives] == [
        "params", "grads"] * len(units), (
        "the collectives are named %r, not the units' parameter gathers and "
        "gradient scatters in that order: a unit that mixes its parameters with "
        "another's gradients is not a wrap unit"
        % ([collective.name for collective in plan.collectives][:6],))
    for index, collective in enumerate(plan.collectives):
        assert collective.axis == "dp", (
            "collective %d is on the %r axis, not `dp`"
            % (index, collective.axis))
        assert collective.group == ranks, (
            "collective %d runs over %r, not the world's own rank order %r"
            % (index, collective.group, ranks))
        assert collective.algo == "gather-scatter", (
            "collective %d is run as %r, not a gather-scatter"
            % (index, collective.algo))
        assert fabric.legality_problems(ring8, collective.plan) == (), (
            "collective %d is not legal on ring(8): %r"
            % (index, fabric.legality_problems(ring8, collective.plan)))
        moved = _moved_per_rank(collective.plan, collective.group)
        assert moved == collective.length, (
            "the %r collective of unit %d declares %r elements per rank but its "
            "own transfers move %r: the length is what the plan moves per rank"
            % (collective.name, index // 2, collective.length, moved))

    for index, unit in enumerate(units):
        gather = plan.collectives[2 * index]
        scatter = plan.collectives[2 * index + 1]
        words = _words(tensors, unit, rate, element)
        per_rank = words * (total - 1) // total
        assert gather.length == per_rank and scatter.length == per_rank, (
            "unit %d declares %r and %r elements per rank, not the recomputed "
            "%r = words * (N-1) / N" % (index, gather.length, scatter.length, per_rank))
        buffer = element * words
        assert _plan_buffer_bytes(gather.plan, element) == buffer, (
            "unit %d all-gathers %r bytes, not its own %r-byte parameter buffer"
            % (index, _plan_buffer_bytes(gather.plan, element), buffer))
        assert _plan_buffer_bytes(scatter.plan, element) == buffer, (
            "unit %d's gradient reduce-scatter is issued over %r bytes, not the "
            "%r bytes of the same unit's buffer"
            % (index, _plan_buffer_bytes(scatter.plan, element), buffer))

    sizes = [_plan_buffer_bytes(plan.collectives[2 * index].plan, element)
             for index in range(len(units))]
    assert sizes == [_words(tensors, unit, rate, element) * element
                     for unit in units], (
        "the units' buffers are %r, not the %r their tensors come to: a plan "
        "that all-gathers the whole model pays one buffer for every unit"
        % (sizes[:3], [_words(tensors, unit, rate, element) * element
                       for unit in units][:3]))

    # ---- the bytes: two passes of the bf16 buffer, derived from the plan ----

    words = model.ceil_div(params * rate, element)
    assert words == 546_612_224, (
        "the fixture changed: 1b's bf16 parameters are %r words" % (words,))
    per_rank_bytes = stage_01.plan_bytes(plan)
    recomputed = 2 * sum(
        element * (_words(tensors, unit, rate, element) * (total - 1) // total)
        for unit in units)
    assert per_rank_bytes == recomputed, (
        "the step moves %r bytes per rank, not the %r its own collectives come "
        "to: the figure is read off the plan, never declared"
        % (per_rank_bytes, recomputed))
    assert per_rank_bytes == 2 * element * (words * (total - 1) // total), (
        "the step moves %r bytes per rank, not the recomputed two passes of the "
        "bf16 parameter buffer — the all-gather of the parameters and the "
        "reduce-scatter of the gradients" % (per_rank_bytes,))
    assert per_rank_bytes == 4 * params * (total - 1) // total == 3_826_285_568, (
        "the 1b/ring(8) step moves %r bytes per rank, not 4P(N-1)/N"
        % (per_rank_bytes,))
    zeroed = stage_03.zero(one_b, ring8, stage=2)
    assert stage_01.plan_bytes(zeroed) == per_rank_bytes, (
        "the fully sharded step moves %r bytes per rank, ZeRO-2's %r: the same "
        "two passes cross the fabric, and only where the buffers live differs"
        % (per_rank_bytes, stage_01.plan_bytes(zeroed)))
    assert len(zeroed.collectives) == 2 and len(plan.collectives) == 44, (
        "ZeRO-2 issues %d collectives and ZeRO-3 %d: the saving is the unit's "
        "residence, not the bytes" % (len(zeroed.collectives), len(plan.collectives)))

    # ---- the ledger: sixteen bytes per parameter, sharded ------------------

    want_memory = (
        stage_01.MemoryLine("params", ranks, model.ceil_div(rate * params, total)),
        stage_01.MemoryLine("gradients", ranks, model.ceil_div(rate * params, total)),
        stage_01.MemoryLine("masters", ranks,
                            model.ceil_div(model.MASTER_BYTES * params, total)),
        stage_01.MemoryLine("optimizer", ranks,
                            model.ceil_div(model.OPTIMIZER_BYTES * params, total)),
        stage_01.MemoryLine("activations", ranks, one_b.activation_bytes(1, 1)),
    )
    assert plan.memory == want_memory, (
        "the ledger is %r, not %r: every one of the sixteen bytes per parameter "
        "is sharded over the group, and the activations are resident"
        % (plan.memory, want_memory))
    assert sum(line.bytes for line in plan.memory[:4]) == 16 * params // total, (
        "the sharded state is %r bytes per rank, not 16P/N"
        % (sum(line.bytes for line in plan.memory[:4]),))
    assert plan.memory[4].bytes == 779_520, (
        "the activation line is %r bytes for one token of 1b, not the shape's "
        "own arithmetic" % (plan.memory[4].bytes,))
    assert [line.what for line in plan.memory] == [
        "params", "gradients", "masters", "optimizer", "activations"], (
        "the ledger reports %r, not the kinds in the frozen order"
        % ([line.what for line in plan.memory],))

    # ---- in_flight: the resident shard, the gathered unit, the activations --

    resident = sum(line.bytes for line in plan.memory)
    assert resident == 16 * params // total + one_b.activation_bytes(1, 1), (
        "the resident ledger is %r bytes per rank, not the shard plus the "
        "activations" % (resident,))
    transient = max(_plan_buffer_bytes(collective.plan, element)
                    for collective in plan.collectives)
    assert transient == rate * max(sum(tensors[index].elements for index in unit)
                                   for unit in units) == 131_072_000, (
        "the largest buffer in flight is %r bytes, not the biggest unit's own "
        "parameters" % (transient,))
    assert s.in_flight(plan) == resident + transient, (
        "the peak is %r bytes, not the resident ledger %r plus the %r-byte unit "
        "in flight" % (s.in_flight(plan), resident, transient))
    assert s.in_flight(plan) == 16 * params // total + one_b.activation_bytes(
        1, 1) + rate * tensors[0].elements, (
        "the peak is %r bytes, not 16P/N plus the activations plus the largest "
        "unit's parameters" % (s.in_flight(plan),))
    assert s.in_flight(plan) == 2_318_300_416, (
        "the 1b/ring(8) peak is %r bytes, not the recomputed "
        "2P + 2 x 65536000 + 779520" % (s.in_flight(plan),))
    assert s.in_flight(plan) != 16 * params // total + transient, (
        "the peak %r counts the unit but not the activations: a figure that "
        "leaves the activations out is exactly the one a rank runs out of "
        "memory on" % (s.in_flight(plan),))

    model_wide = s.fully_sharded(one_b, ring8, wrap_bytes=2 * params)
    assert len(model_wide.collectives) == 2, (
        "a budget that holds the model still issues %d collectives"
        % (len(model_wide.collectives),))
    assert s.in_flight(model_wide) == resident + rate * params, (
        "gathering the whole model at once peaks at %r bytes, not the resident "
        "ledger plus the model's own parameters"
        % (s.in_flight(model_wide),))
    assert s.in_flight(model_wide) > s.in_flight(plan), (
        "one unit for the whole model peaks at %r bytes, no more than the "
        "one-layer wrap's %r: the unit at a time is the whole saving"
        % (s.in_flight(model_wide), s.in_flight(plan)))

    message = _refuses(model.ModelError, "a plan that is not a StepPlan",
                       lambda: s.in_flight(b"not a plan"))
    assert "plan" in message, (
        "the refusal of a non-StepPlan does not name it: %r" % (message,))

    # ---- the axis of one is the single-device reference -------------------

    sole = s.fully_sharded(one_b, fabric.full(1), wrap_bytes=wrap)
    assert sole.collectives == (), (
        "an axis of one issues %r collectives, not none: a rank alone is "
        "already holding every shard" % (sole.collectives,))
    assert sum(line.bytes for line in sole.memory[:4]) == 16 * params, (
        "the one-rank state is %r bytes per rank, not the reference 16 per "
        "parameter" % (sum(line.bytes for line in sole.memory[:4]),))
    assert s.in_flight(sole) == 16 * params + one_b.activation_bytes(1, 1), (
        "the one-rank peak is %r bytes, not the reference state plus the "
        "activations" % (s.in_flight(sole),))

    # ---- the batch and the sequence the activations are priced for ---------

    assert s.fully_sharded(one_b, ring8, wrap_bytes=wrap, batch=1, seq=1) == plan, (
        "the one-token default is not batch=1, seq=1: the plan changed")
    other = s.fully_sharded(one_b, ring8, wrap_bytes=wrap, batch=2, seq=3)
    assert other.collectives == plan.collectives, (
        "the batch and the sequence changed the collectives: they price the "
        "activations, not the fabric")
    assert other.memory[4] == stage_01.MemoryLine(
        "activations", ranks, one_b.activation_bytes(2, 3)), (
        "the activation line for batch=2, seq=3 is %r, not the shape's own "
        "arithmetic for it" % (other.memory[4],))
    assert s.in_flight(other) == s.in_flight(plan) + (
        one_b.activation_bytes(2, 3) - one_b.activation_bytes(1, 1)), (
        "the peak for batch=2, seq=3 is %r, not the one-token peak plus the "
        "extra activations" % (s.in_flight(other),))
    assert s.fully_sharded(one_b, ring8, wrap_bytes=wrap) == plan, (
        "two calls of fully_sharded(1b, ring(8)) return different steps: a plan "
        "is a function of its inputs")

    # ---- the refusals -----------------------------------------------------

    message = _refuses(model.ModelError, "a budget below one layer",
                       lambda: s.fully_sharded(one_b, ring8, wrap_bytes=wrap - 1))
    assert "layer" in message, (
        "the refusal of a one-layer-minus-one budget does not name the unit: %r"
        % (message,))
    for bad in (0, True, "2"):
        message = _refuses(
            model.ModelError, "a batch of %r" % (bad,),
            lambda bad=bad: s.fully_sharded(one_b, ring8, wrap_bytes=wrap,
                                            batch=bad))
        assert "batch" in message, (
            "the refusal of batch=%r does not name it: %r" % (bad, message))
    message = _refuses(model.ModelError, "a sequence of zero",
                       lambda: s.fully_sharded(one_b, ring8, wrap_bytes=wrap, seq=0))
    assert "seq" in message, (
        "the refusal of seq=0 does not name it: %r" % (message,))
    message = _refuses(model.ModelError, "a shape that is not a ModelShape",
                       lambda: s.fully_sharded("1b", ring8, wrap_bytes=wrap))
    assert "shape" in message, (
        "the refusal of a non-ModelShape does not name the shape: %r" % (message,))
    message = _refuses(fabric.FabricError, "a world that is not a fabric",
                       lambda: s.fully_sharded(one_b, None, wrap_bytes=wrap))
    assert "world" in message or "None" in message, (
        "the refusal of a non-fabric world does not name it: %r" % (message,))

    # ---- the tiny model's own collectives, run on the fabric ---------------

    tiny = model.SHAPES["tiny"]
    two = fabric.full(2)
    tiny_tensors = tiny.tensors()
    assert tiny.params() == 388 and len(tiny_tensors) == 16, (
        "the fixture changed: tiny has %d parameters and %d tensors"
        % (tiny.params(), len(tiny_tensors)))
    tiny_layer = sum(tensor.elements for tensor in tiny_tensors[1:8])
    tiny_wrap = model.PARAM_BYTES * tiny_layer
    tiny_units = s.wrap_policy(tiny, two, wrap_bytes=tiny_wrap)
    tiny_plan = s.fully_sharded(tiny, two, wrap_bytes=tiny_wrap)
    assert len(tiny_units) == 2 + tiny.layers == 4, (
        "tiny's one-layer budget makes %d units, not its embedding, its two "
        "layers and its norm" % (len(tiny_units),))
    assert len(tiny_plan.collectives) == 8, (
        "tiny's plan issues %d collectives, not four units' four pairs"
        % (len(tiny_plan.collectives),))
    for collective in tiny_plan.collectives:
        assert fabric.legality_problems(two, collective.plan) == (), (
            "tiny's %r collective is not legal on full(2): %r"
            % (collective.name, fabric.legality_problems(two, collective.plan)))

    words = _words(tiny_tensors, tiny_units[0], model.PARAM_BYTES, element)
    assert words == 24 and words % 2 == 0, (
        "the tiny embedding's buffer is %r words over two ranks" % (words,))
    buffers = fabric.buffers(2, words)
    shard = words // 2
    gathered = fabric.run(two, tiny_plan.collectives[0].plan, buffers)
    for rank in two.ranks:
        assert gathered[rank][:shard] == buffers[two.ranks[0]][:shard], (
            "rank %r does not hold r0's shard after the unit's all-gather"
            % (rank,))
        assert gathered[rank][shard:] == buffers[two.ranks[1]][shard:], (
            "rank %r does not hold r1's shard after the unit's all-gather"
            % (rank,))
    whole_sum = fabric.reference(buffers)
    reduced = fabric.run(two, tiny_plan.collectives[1].plan, buffers)
    seen = reduced[two.ranks[0]][:shard] + reduced[two.ranks[1]][shard:]
    assert seen == whole_sum, (
        "the unit's gradient shards reassemble to %r, not the reference sum "
        "%r: the reduce-scatter is what sums them, and shard c ends on rank c"
        % (seen[:4], whole_sum[:4]))

    print("check_04: a wrap unit is a whole module and never the model — one "
          "all-gather of its parameters and one reduce-scatter of its gradients "
          "per unit, 2P(N-1)/N bytes each way per rank, 16P/N resident with "
          "every kind of state sharded, and the peak is the resident shard plus "
          "the largest unit in flight plus the activations")

# --- stage 5 -----------------------------------------------------------------------
def check_5():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("H1_REPO"), start, os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "distributed-training-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set H1_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call):
        """The message of the refusal `call` must raise, or the mistake named.

        Only the stage's own refusal type is caught, and `NotImplementedError` is
        let through unharmed: an untouched template must surface as `TODO`, never as
        a failed assertion. A return, or any other exception, is the mistake `what`
        names.
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

    import fabric
    import model
    import plans

    import stage_01 as s1
    import stage_05 as s

    # ---- the fixture matrices, and the reference they must reproduce -------

    x = ((1, 2, 3, 4), (5, 6, 7, 8))          # two tokens, inner dimension 4
    a_rows = tuple(tuple((t * 2 + k * 3) % 5 - 2 for k in range(4))
                   for t in range(8))          # the first projection: 8 neurons
    b_rows = tuple(tuple((t * 3 + j) % 5 - 2 for j in range(4))
                   for t in range(8))          # the second: one row per feature
    bias = (7, -3, 2, 5)
    # The block's single-matrix equivalent, exactly: w = B^T A.
    w = tuple(tuple(sum(b_rows[t][j] * a_rows[t][k] for t in range(8))
                    for k in range(4)) for j in range(4))
    reference = model.reference_layer(x, w, bias)
    bare = model.reference_layer(x, w, (0, 0, 0, 0))

    full4 = fabric.full(4)
    g4 = full4.ranks
    switch8 = fabric.switch(8, width=4)
    g8 = switch8.ranks
    g4a = ("r0", "r1", "r2", "r3")             # one switch group: four cheap ranks

    def block(rows, index, count):
        """The `index`-th of `count` contiguous blocks of `rows`."""
        step = len(rows) // count
        return rows[index * step:(index + 1) * step]

    def halves(ranks):
        """`f` then `g` on every rank's own blocks: the row half's partials."""
        count = len(ranks)
        shards = [s.f(x, block(a_rows, i, count)) for i in range(count)]
        return [s.g(shards[i], block(b_rows, i, count)) for i in range(count)]

    def combine(partials):
        """What the forward all-reduce leaves: the partials summed, plus the
        bias the row half owns."""
        return tuple(tuple(bias[j] + sum(part[row][j] for part in partials)
                           for j in range(4)) for row in range(len(x)))

    # ---- the column half: disjoint shards, no fabric -----------------------

    shards = [s.column_parallel(x, block(a_rows, i, 4)) for i in range(4)]
    whole = tuple(tuple(value for shard in shards for value in shard[row])
                  for row in range(len(x)))
    assert whole == model.reference_layer(x, a_rows, (0,) * 8), (
        "the column half's four shards concatenate to %r, not the projection %r: "
        "a column-parallel rank holds its own columns of the output, in rank "
        "order, and nothing is combined" % (whole, model.reference_layer(x, a_rows, (0,) * 8)))
    assert len(s.column_parallel(x, block(a_rows, 0, 4))) == len(x), (
        "a column-parallel rank answers %r for %d input rows: the shard has one "
        "row per input row and one column per output neuron the rank owns"
        % (s.column_parallel(x, block(a_rows, 0, 4)), len(x)))
    assert len(s.column_parallel(x, block(a_rows, 0, 4))[0]) == 2, (
        "a rank owning two output neurons answers %r: its shard must have two "
        "columns, not the whole projection's"
        % (s.column_parallel(x, block(a_rows, 0, 4))[0],))
    assert all(isinstance(value, int) and not isinstance(value, bool)
               for row in whole for value in row), (
        "the column half answered %r: every entry is an int" % (whole,))

    # ---- the row half: slicing w into column blocks, summed ----------------

    w_columns = tuple(tuple(w[j][k] for j in range(4)) for k in range(4))
    partials = []
    for index in range(4):
        columns = (index,)
        x_block = tuple(tuple(row[c] for c in columns) for row in x)
        w_block = tuple(w_columns[c] for c in columns)
        partials.append(s.row_parallel(x_block, w_block))
    summed = tuple(tuple(sum(part[row][j] for part in partials) for j in range(4))
                   for row in range(len(x)))
    assert summed == bare, (
        "slicing w into four column blocks, applying the row half on each and "
        "summing gives %r, not the reference's matmul %r: a row-parallel rank "
        "contracts its own block of the weight's columns and the partials sum"
        % (summed, bare))
    two = [s.row_parallel(tuple(tuple(row[c] for c in (i, i + 1)) for row in x),
                          tuple(w_columns[c] for c in (i, i + 1)))
           for i in (0, 2)]
    assert tuple(tuple(sum(part[row][j] for part in two) for j in range(4))
                 for row in range(len(x))) == bare, (
        "the same weight in two blocks of two columns sums to %r, not %r: the "
        "answer must not depend on how many ranks the block is split over"
        % (summed, bare))

    # ---- the block: f then g over the group, combined by the all-reduce ----

    for world, ranks in ((full4, g4), (switch8, g8), (switch8, g4a)):
        got = combine(halves(ranks))
        assert got == reference, (
            "the block over %d ranks of %s answers %r, not the reference %r: f "
            "(the column half) then g (the row half) on every rank's own blocks, "
            "summed by the forward all-reduce, must reproduce reference_layer "
            "exactly — and the split must not change the answer"
            % (len(ranks), world.name, got, reference))
    shard0 = s.f(x, block(a_rows, 0, 4))
    assert len(shard0[0]) == 2 and len(s.g(shard0, block(b_rows, 0, 4))[0]) == 4, (
        "f answers %r and g answers %r for a rank owning a quarter of the "
        "block: the column half answers the rank's own output neurons (two "
        "columns) and the row half the whole projection's output (four), as "
        "partials" % (shard0, s.g(shard0, block(b_rows, 0, 4))))

    # ---- the matrices the halves refuse ------------------------------------

    message = _refuses(model.ModelError, "a weight whose inner dimension differs",
                       lambda: s.column_parallel(x, ((1, 2, 3), (4, 5, 6))))
    assert "inner" in message, (
        "the refusal of a mismatched inner dimension does not name it: %r" % (message,))
    _refuses(model.ModelError, "a weight that is not a matrix",
             lambda: s.column_parallel(x, 5))
    _refuses(model.ModelError, "an input that is not a matrix",
             lambda: s.column_parallel(5, block(a_rows, 0, 4)))
    _refuses(model.ModelError, "a ragged matrix",
             lambda: s.column_parallel(x, ((1, 2, 3, 4), (1, 2))))
    _refuses(model.ModelError, "a row that is not a tuple",
             lambda: s.column_parallel(x, ([1, 2, 3, 4], [5, 6, 7, 8])))
    _refuses(model.ModelError, "a bool element",
             lambda: s.column_parallel(x, ((1, 2, 3, True), (1, 2, 3, 4))))
    _refuses(model.ModelError, "a weight with no rows",
             lambda: s.row_parallel(x, ()))
    message = _refuses(model.ModelError, "a row-half weight whose rows differ "
                       "from the shard's columns",
                       lambda: s.row_parallel(x, block(b_rows, 0, 4)))
    assert "columns" in message or "rows" in message, (
        "the refusal of a row-half shape mismatch does not name it: %r" % (message,))

    # ---- the block's plan: two all-reduces, sized by the activation --------

    tiny = model.SHAPES["tiny"]
    assert (tiny.layers, tiny.hidden, tiny.ffn_hidden) == (2, 4, 8), (
        "the fixture changed: tiny is %r" % (tiny,))

    batch, seq = 2, 3
    elements = batch * seq * tiny.hidden
    plan = s.tensor_parallel(tiny, full4, group=g4, batch=batch, seq=seq)
    assert isinstance(plan, s1.StepPlan), (
        "the block's plan is %r, not the frozen StepPlan" % (type(plan).__name__,))
    assert [c.name for c in plan.collectives] == ["activations", "grads"], (
        "the block issues %r, not the two all-reduces (activations, grads): the "
        "forward combines the row half's partials and the backward combines the "
        "column half's gradient partials, and one all-reduce per block leaves "
        "one of them uncombined"
        % ([c.name for c in plan.collectives],))
    assert [c.axis for c in plan.collectives] == ["tp", "tp"], (
        "the block's collectives run on the %r axis, not tp"
        % ([c.axis for c in plan.collectives],))
    assert [c.group for c in plan.collectives] == [g4, g4], (
        "the block's collectives run over %r, not the world's rank order %r"
        % ([c.group for c in plan.collectives], g4))
    assert [c.length for c in plan.collectives] == [elements, elements], (
        "the block's all-reduces move %r elements per rank, not batch*seq*hidden "
        "= %d twice: the tensor at the row-parallel boundary is the block's "
        "activation of %d elements, not the FFN's intermediate (ffn_hidden=%d, "
        "%d elements) and not the whole layer's"
        % ([c.length for c in plan.collectives], elements, elements,
           tiny.ffn_hidden, batch * seq * tiny.ffn_hidden))
    for collective in plan.collectives:
        problems = fabric.legality_problems(full4, collective.plan)
        assert problems == (), (
            "the block's %r collective is not legal on %s: %r"
            % (collective.name, full4.name, problems))
    assert plan.compute == 0, (
        "the block's plan carries %r ticks of compute: the traffic the block adds "
        "is its two all-reduces, and the compute belongs to the step's own "
        "ComputeModel" % (plan.compute,))
    assert plan.memory == (), (
        "the block's plan carries the ledger %r: the state is stage 1's "
        "plan_memory, and this plan is traffic" % (plan.memory,))
    assert s1.plan_bytes(plan) == 2 * fabric.ELEMENT_BYTES * elements, (
        "the block moves %r bytes per rank, not two collectives of %d elements "
        "at %d bytes each"
        % (s1.plan_bytes(plan), elements, fabric.ELEMENT_BYTES))
    assert s1.network_bytes(plan) == 2 * fabric.ELEMENT_BYTES * elements * 4, (
        "the block puts %r bytes on the network, not the per-rank figure times "
        "the four ranks" % (s1.network_bytes(plan),))

    # ---- the algorithm is recomputed, not fixed ----------------------------

    def priced(world, ranks, length):
        """`[(candidates that fit, priced)]`, in the order ties are broken."""
        found = []
        for name, build in (("ring", plans.ring_allreduce),
                            ("tree", plans.tree_allreduce),
                            ("doubling", plans.doubling_allreduce)):
            try:
                candidate = build(world, ranks, length)
            except fabric.FabricError:
                continue
            found.append((name, s1.plan_ticks(world, candidate), candidate))
        return found

    def cheapest(found):
        """The first candidate of the smallest price."""
        best = None
        for name, ticks, candidate in found:
            if best is None or ticks < best[1]:
                best = (name, ticks, candidate)
        return best

    on_full = cheapest(priced(full4, g4, elements))
    assert on_full[0] == "tree", (
        "the fixture changed: on %s the cheapest all-reduce of %d elements is %r"
        % (full4.name, elements, on_full[0]))
    on_switch = cheapest(priced(switch8, g8, elements))
    assert on_switch[0] == "tree" and on_switch[0] != "ring", (
        "the fixture changed: on %s the cheapest all-reduce of %d elements is %r"
        % (switch8.name, elements, on_switch[0]))
    assert [c.algo for c in plan.collectives] == [on_full[0]] * 2, (
        "the block's algorithm is %r, not %r: the cheapest all-reduce `plans.py` "
        "can build here, priced by stage 1 — a fixed algorithm is a size table"
        % ([c.algo for c in plan.collectives], on_full[0]))
    for collective in plan.collectives:
        ticks = s1.plan_ticks(full4, collective.plan)
        assert ticks == on_full[1], (
            "the block's plan costs %d ticks, not the %d of the %r plan bound to "
            "the name it carries: the label must be the plan" % (ticks, on_full[1], collective.algo))
    assert s1.step_ticks(full4, plan) == 2 * on_full[1], (
        "the block's step costs %r ticks, not its two all-reduces' %d: comms "
        "overlap compute, and the plan's comms is the sum of its collectives"
        % (s1.step_ticks(full4, plan), 2 * on_full[1]))

    plan8 = s.tensor_parallel(tiny, switch8, group=g8, batch=batch, seq=seq)
    assert [c.algo for c in plan8.collectives] == [on_switch[0]] * 2, (
        "on %s the block's algorithm is %r, not %r: the ring is %d ticks there "
        "and the butterfly cannot cross the spine"
        % (switch8.name, [c.algo for c in plan8.collectives], on_switch[0],
           cheapest(priced(switch8, g8, elements))[1]))
    for collective in plan8.collectives:
        problems = fabric.legality_problems(switch8, collective.plan)
        assert problems == (), (
            "the block's %r collective is not legal on %s: %r"
            % (collective.name, switch8.name, problems))
    assert s1.step_ticks(switch8, plan8) == 2 * on_switch[1], (
        "on %s the block's step costs %r ticks, not its two all-reduces' %d"
        % (switch8.name, s1.step_ticks(switch8, plan8), 2 * on_switch[1]))

    # ---- the plan, run on the fabric, is the block's own all-reduce --------

    for world, ranks in ((full4, g4), (switch8, g8)):
        count = len(ranks)
        partials = halves(ranks)
        flat = tuple(value for part in partials for row in part for value in row)
        length = len(flat) // count
        one_token = s.tensor_parallel(tiny, world, group=ranks, batch=len(x), seq=1)
        assert [c.length for c in one_token.collectives] == [length, length], (
            "the block's all-reduce is %r elements per rank, not the %d its own "
            "partial tensors carry: the length is batch*seq*hidden of what is "
            "being combined" % ([c.length for c in one_token.collectives], length))
        buffers = {ranks[i]: tuple(flat[i * length:(i + 1) * length])
                   for i in range(count)}
        topology = plans.group_fabric(world, ranks)
        combined = fabric.run(topology, one_token.collectives[0].plan, buffers,
                              op="sum")
        want = tuple(sum(buffers[rank][index] for rank in ranks)
                     for index in range(length))
        assert combined[ranks[0]] == want, (
            "the block's forward collective, run on %s, leaves %r, not the "
            "element-wise sum of the ranks' partials %r: the plan must be the "
            "all-reduce the row half needs"
            % (topology.name, combined[ranks[0]], want))
        flattened = tuple(bias[j] + want[row * tiny.hidden + j]
                          for row in range(len(x)) for j in range(tiny.hidden))
        assert flattened == tuple(value for row in reference for value in row), (
            "the collective's own sum plus the bias is %r, not the reference's "
            "rows %r" % (flattened, tuple(value for row in reference for value in row)))

    # ---- one rank: no collective, no cost ----------------------------------

    alone = s.tensor_parallel(tiny, full4, group=("r2",), batch=batch, seq=seq)
    assert alone == s1.StepPlan(collectives=(), compute=0, memory=()), (
        "a tensor parallel over one rank is %r, not the empty plan: a collective "
        "over one rank combines nothing and must not be charged" % (alone,))
    assert s1.plan_bytes(alone) == 0 and s1.network_bytes(alone) == 0, (
        "a group of one moves %r bytes per rank and %r on the network, not none"
        % (s1.plan_bytes(alone), s1.network_bytes(alone)))
    assert s1.step_ticks(full4, alone) == 0, (
        "a group of one costs %r ticks, not none" % (s1.step_ticks(full4, alone),))

    # ---- the group's order, the tokens and the refusals --------------------

    shuffled = s.tensor_parallel(tiny, full4, group=("r3", "r1", "r0", "r2"),
                                 batch=batch, seq=seq)
    assert [c.group for c in shuffled.collectives] == [g4, g4], (
        "a group handed in any order comes back as %r, not the world's rank "
        "order %r: a plan's rank order is the world's, never the caller's"
        % ([c.group for c in shuffled.collectives], g4))
    assert s.tensor_parallel(tiny, full4, group=g4, batch=batch, seq=seq) == plan, (
        "two calls with equal arguments returned unequal plans: a plan is a "
        "function of its inputs")
    assert s.tensor_parallel(tiny, full4, group=g4) == s.tensor_parallel(
        tiny, full4, group=g4, batch=1, seq=1), (
        "the one-token default is not batch=1, seq=1: %r"
        % (s.tensor_parallel(tiny, full4, group=g4),))

    message = _refuses(model.ModelError, "a batch that is not a positive count",
                       lambda: s.tensor_parallel(tiny, full4, group=g4, batch=0))
    assert "batch" in message, (
        "the refusal of a bad batch does not name it: %r" % (message,))
    message = _refuses(model.ModelError, "a bool seq",
                       lambda: s.tensor_parallel(tiny, full4, group=g4, seq=True))
    assert "seq" in message, (
        "the refusal of a bad seq does not name it: %r" % (message,))
    message = _refuses(model.ModelError, "a shape that is not a ModelShape",
                       lambda: s.tensor_parallel(4, full4, group=g4))
    assert "shape" in message, (
        "the refusal of a bad shape does not name it: %r" % (message,))
    message = _refuses(fabric.FabricError, "a rank the world does not have",
                       lambda: s.tensor_parallel(tiny, full4, group=("r0", "r9")))
    assert "r9" in message, (
        "the refusal of an unknown rank does not name it: %r" % (message,))
    _refuses(fabric.FabricError, "a rank named twice",
             lambda: s.tensor_parallel(tiny, full4, group=("r0", "r0")))
    _refuses(fabric.FabricError, "an empty group",
             lambda: s.tensor_parallel(tiny, full4, group=()))
    _refuses(fabric.FabricError, "a group that is not a tuple",
             lambda: s.tensor_parallel(tiny, full4, group=["r0", "r1"]))

    print("check_05: tensor parallel — column_parallel is the rank's own columns "
          "of the projection and row_parallel its partials, f/g compose to "
          "reference_layer exactly over any split, and the block's plan is the "
          "two all-reduces of batch*seq*hidden elements, the cheapest plans.py "
          "builds, empty over a group of one")

# --- stage 6 -----------------------------------------------------------------------
def check_6():
    import math
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("H1_REPO"), start, os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "distributed-training-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set H1_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call):
        """The message of the refusal `call` must raise, or the mistake named.

        Only the stage's own refusal type is caught, and `NotImplementedError` is
        let through unharmed: an untouched template must surface as `TODO`, never as
        a failed assertion. A return, or any other exception, is the mistake `what`
        names.
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

    import model
    import stage_06 as s

    Slot = s.Slot

    def say(label, detail):
        print("check_06: %s — %s" % (label, detail))

    def _pair(pair, want, what):
        """The exact fraction `pair`, valid and equal to `want`, or the mistake."""
        assert isinstance(pair, tuple) and len(pair) == 2, (
            "%s is %r, not an (idle, total) pair" % (what, pair))
        for value in pair:
            assert isinstance(value, int) and not isinstance(value, bool), (
                "%s is %r: a fraction is an exact pair of ints, never a float" % (what, pair))
        numerator, denominator = pair
        assert denominator > 0, (
            "%s has denominator %r, not a positive int" % (what, denominator))
        assert math.gcd(numerator, denominator) == 1, (
            "%s is %r, not reduced to lowest terms" % (what, pair))
        assert pair == want, "%s is %r, not %r" % (what, pair, want)

    def _replayed(schedule, p):
        """The bubble as the slot list itself says it: the idle (stage, step)
        pairs inside the makespan, an independent replay of the data."""
        pairs = {(x.stage, x.step) for x in schedule}
        makespan = max(x.step for x in schedule)
        return p * makespan - len(pairs), makespan, len(pairs)

    def _expect(schedule, p, m, label):
        """The structural contract every schedule must keep."""
        assert isinstance(schedule, tuple), (
            "%s is %r, not a tuple of Slots: a schedule is frozen data"
            % (label, type(schedule).__name__))
        for slot in schedule:
            assert isinstance(slot, Slot), (
                "%s holds %r, not a Slot" % (label, slot))
        assert len(schedule) == 2 * p * m, (
            "%s carries %d slots, not 2*p*m = %d: each micro-batch runs its "
            "forward and its backward through each stage exactly once"
            % (label, len(schedule), 2 * p * m))
        keys = [(x.micro_batch, x.stage, x.phase) for x in schedule]
        dupes = sorted(k for k in set(keys) if keys.count(k) > 1)
        assert not dupes, (
            "%s runs a (micro_batch, stage, phase) twice: %r — a schedule never "
            "forwards a micro-batch through a stage twice" % (label, dupes))
        want = sorted((mu, st, ph) for mu in range(m)
                      for st in range(p) for ph in ("f", "b"))
        assert sorted(keys) == want, (
            "%s misses a micro-batch's task through a stage: it has %r"
            % (label, sorted(keys)))
        canonical = tuple(sorted(schedule,
                                 key=lambda x: (x.step, x.stage, x.phase, x.micro_batch)))
        assert schedule == canonical, (
            "%s is not canonical: sorted by (step, stage, phase, micro_batch) it "
            "is %r" % (label, canonical))
        at = {(x.micro_batch, x.stage, x.phase): x.step for x in schedule}
        for mu in range(m):
            for st in range(p):
                assert at[(mu, st, "f")] == mu + st + 1, (
                    "%s forwards micro-batch %d through stage %d at step %d, not "
                    "mu+s+1 = %d" % (label, mu, st, at[(mu, st, "f")], mu + st + 1))
                assert at[(mu, st, "b")] > at[(mu, st, "f")], (
                    "%s back-propagates micro-batch %d's stage %d at step %d, not "
                    "after its forward there at step %d: a backward never shares a "
                    "step with its own micro-batch's forward"
                    % (label, mu, st, at[(mu, st, "b")], at[(mu, st, "f")]))

    # ---- GPipe at (4, 8): 22 steps, 24 idle pairs of 88, exits descending ----

    gpipe = s.gpipe(4, 8)
    _expect(gpipe, 4, 8, "gpipe(4, 8)")
    fmax = max(x.step for x in gpipe if x.phase == "f")
    bmin = min(x.step for x in gpipe if x.phase == "b")
    assert fmax < bmin, (
        "gpipe(4, 8) runs a backward at step %d before every forward is done "
        "(last forward %d): GPipe does every forward, then every backward"
        % (bmin, fmax))
    idle, makespan, pairs = _replayed(gpipe, 4)
    assert makespan == 22, (
        "gpipe(4, 8)'s makespan is %d, not 22 (2m + 2p - 2)" % (makespan,))
    assert idle == 24, (
        "replaying gpipe(4, 8) leaves %d idle (stage, step) pairs, not 24" % (idle,))
    assert pairs == 64, (
        "gpipe(4, 8) spends %d busy (stage, step) pairs, not the 2*p*m = 64 its "
        "tasks need" % (pairs,))
    assert s.bubble(gpipe, 4) == 24, (
        "bubble(gpipe(4, 8), 4) is %r, not the 24 pairs the replay shows: the "
        "bubble is read off the schedule, not a formula that ignores the "
        "micro-batches" % (s.bubble(gpipe, 4),))
    _pair(s.bubble_fraction(4, 8, schedule=gpipe), (3, 11), "bubble_fraction(4, 8, gpipe)")
    assert s.replay(gpipe, 4, 8) == (22, 21, 20, 19, 18, 17, 16, 15), (
        "gpipe(4, 8)'s exit steps are %r, not descending (22, …, 15): GPipe's "
        "backwards run in reverse micro-batch order"
        % (s.replay(gpipe, 4, 8),))
    say("gpipe(4, 8)", "64 slots, forwards 1..11, 24/88 idle = 3/11, exits 22..15")

    # ---- 1F1B at (4, 8): 15 steps, 12 idle pairs of 60, exits ascending ------

    one = s.one_f_one_b(4, 8)
    _expect(one, 4, 8, "one_f_one_b(4, 8)")
    assert not max(x.step for x in one if x.phase == "f") \
        < min(x.step for x in one if x.phase == "b"), (
        "one_f_one_b(4, 8) runs every forward before every backward: that is "
        "GPipe with no warm-up or cool-down, not 1F1B")
    sf = {(x.stage, x.step) for x in one if x.phase == "f"}
    sb = {(x.stage, x.step) for x in one if x.phase == "b"}
    assert sf & sb, (
        "one_f_one_b(4, 8) never lays a forward and a backward into the same "
        "(stage, step): its stages are idle where they should stream")
    idle, makespan, pairs = _replayed(one, 4)
    assert makespan == 15, (
        "one_f_one_b(4, 8)'s makespan is %d, not 15 (m + 2p - 1)" % (makespan,))
    assert idle == 12, (
        "replaying one_f_one_b(4, 8) leaves %d idle (stage, step) pairs, not 12" % (idle,))
    assert len(one) > len({(x.stage, x.step) for x in one}), (
        "one_f_one_b(4, 8) is %r: 1F1B double-books steps (64 slots over 48 "
        "pairs), and a bubble that counts a step twice would miss that"
        % (len(one),))
    assert s.bubble(one, 4) == 12, (
        "bubble(one_f_one_b(4, 8), 4) is %r, not 12: the same steps carry two "
        "tasks, and counting slots instead of pairs gets this wrong"
        % (s.bubble(one, 4),))
    _pair(s.bubble_fraction(4, 8, schedule=one), (1, 5), "bubble_fraction(4, 8, 1F1B)")
    assert s.replay(one, 4, 8) == (8, 9, 10, 11, 12, 13, 14, 15), (
        "one_f_one_b(4, 8)'s exit steps are %r, not ascending (8, …, 15)"
        % (s.replay(one, 4, 8),))
    say("one_f_one_b(4, 8)", "64 slots over 48 pairs, 12/60 idle = 1/5, exits 8..15")

    # ---- the small fixture (2, 3): 1/4 and 1/6 -------------------------------

    g23 = s.gpipe(2, 3)
    _expect(g23, 2, 3, "gpipe(2, 3)")
    assert s.bubble(g23, 2) == 4 and _replayed(g23, 2)[0] == 4, (
        "gpipe(2, 3)'s bubble is %r (replay %r), not 4"
        % (s.bubble(g23, 2), _replayed(g23, 2)[0]))
    _pair(s.bubble_fraction(2, 3, schedule=g23), (1, 4), "bubble_fraction(2, 3, gpipe)")
    b23 = s.one_f_one_b(2, 3)
    _expect(b23, 2, 3, "one_f_one_b(2, 3)")
    assert s.bubble(b23, 2) == 2 and _replayed(b23, 2)[0] == 2, (
        "one_f_one_b(2, 3)'s bubble is %r (replay %r), not 2"
        % (s.bubble(b23, 2), _replayed(b23, 2)[0]))
    _pair(s.bubble_fraction(2, 3, schedule=b23), (1, 6), "bubble_fraction(2, 3, 1F1B)")
    say("(2, 3)", "gpipe 4/16 = 1/4, 1F1B 2/12 = 1/6")

    # ---- p = 1 has no bubble; m = 1 makes the two schedules equal ------------

    for label, schedule in (("gpipe(1, 5)", s.gpipe(1, 5)),
                            ("one_f_one_b(1, 5)", s.one_f_one_b(1, 5))):
        _expect(schedule, 1, 5, label)
        assert s.bubble(schedule, 1) == 0, (
            "%s has bubble %r, not 0: one stage is never idle"
            % (label, s.bubble(schedule, 1)))
        _pair(s.bubble_fraction(1, 5, schedule=schedule), (0, 1),
              "bubble_fraction(1, 5, %s)" % (label,))
    for p in (1, 3, 4):
        assert s.gpipe(p, 1) == s.one_f_one_b(p, 1), (
            "with m = 1 gpipe(%d, 1) and one_f_one_b(%d, 1) differ: one "
            "micro-batch leaves the schedules the same" % (p, p))
    say("p = 1, m = 1", "one stage idles nowhere, one micro-batch equalises the schedules")

    # ---- the last micro-batch's forward leaves the last stage at m + p - 1 ---

    for p, m in ((4, 8), (2, 3), (3, 5), (1, 4)):
        for label, build in (("gpipe", s.gpipe), ("one_f_one_b", s.one_f_one_b)):
            schedule = build(p, m)
            step = max(x.step for x in schedule
                       if x.phase == "f" and x.stage == p - 1 and x.micro_batch == m - 1)
            assert step == m + p - 1, (
                "%s(%d, %d)'s last micro-batch leaves the last stage at step %d, "
                "not m + p - 1 = %d" % (label, p, m, step, m + p - 1))
    say("forward stream", "the last micro-batch's forward leaves the last stage at m + p - 1")

    # ---- a Slot is frozen data -----------------------------------------------

    held = s.gpipe(2, 2)[0]
    try:
        held.step = 0
    except AttributeError:
        pass
    else:
        assert False, (
            "a Slot is mutable: a schedule must be frozen data, not a plan "
            "someone can edit in place")
    say("frozen slots", "a Slot refuses mutation")

    # ---- a hand-built 2x2 schedule the refusals are probed against ----------

    def S(step, stage, micro_batch, phase):
        return Slot(step=step, stage=stage, micro_batch=micro_batch, phase=phase)

    base = tuple(sorted(
        (S(1, 0, 0, "f"), S(2, 0, 1, "f"), S(2, 1, 0, "f"), S(3, 1, 0, "b"),
         S(3, 1, 1, "f"), S(4, 0, 0, "b"), S(4, 1, 1, "b"), S(5, 0, 1, "b")),
        key=lambda x: (x.step, x.stage, x.phase, x.micro_batch)))
    assert isinstance(s.bubble(base, 2), int), (
        "the hand-built 2x2 schedule is refused: %r" % (base,))

    # ---- bad p / m -----------------------------------------------------------

    for build, name in ((s.gpipe, "gpipe"), (s.one_f_one_b, "one_f_one_b")):
        for bad in (0, -1, True, 2.0, "2"):
            message = _refuses(
                model.ModelError, "%s(p=%r, 2)" % (name, bad),
                lambda b=build, x=bad: b(x, 2))
            assert "p" in message, (
                "the refusal of p=%r does not name it: %r" % (bad, message))
        for bad in (0, -1, True, 8.0, "8"):
            message = _refuses(
                model.ModelError, "%s(2, m=%r)" % (name, bad),
                lambda b=build, x=bad: b(2, x))
            assert "m" in message, (
                "the refusal of m=%r does not name it: %r" % (bad, message))
    for what, call in (("bubble_fraction(p=0, 2)", lambda: s.bubble_fraction(0, 2, schedule=base)),
                       ("bubble_fraction(2, m=-1)", lambda: s.bubble_fraction(2, -1, schedule=base)),
                       ("replay(p=0)", lambda: s.replay(base, 0, 2)),
                       ("replay(2, m=True)", lambda: s.replay(base, 2, True))):
        _refuses(model.ModelError, what, call)
    say("bad p / m", "a non-int or non-positive count is refused, naming it")

    # ---- a schedule that is not a tuple of Slots, or holds a non-Slot --------

    for what, call in (("bubble on a list", lambda: s.bubble(list(base), 2)),
                       ("bubble_fraction on a list",
                        lambda: s.bubble_fraction(2, 2, schedule=list(base))),
                       ("replay on a list", lambda: s.replay(list(base), 2, 2))):
        message = _refuses(model.ModelError, what, call)
        assert "tuple" in message, (
            "the refusal of a list schedule does not name the tuple: %r" % (message,))
    for what, call in (("bubble_fraction", lambda: s.bubble_fraction(
            2, 2, schedule=(S(1, 0, 0, "f"), "x"))),
                       ("replay", lambda: s.replay((S(1, 0, 0, "f"), "x"), 2, 2))):
        message = _refuses(model.ModelError, "%s holding a non-Slot" % (what,), call)
        assert "Slot" in message, (
            "the refusal of a non-Slot does not name it: %r" % (message,))
    say("tuple of Slots", "a non-tuple or a non-Slot is refused, naming it")

    # ---- a slot with a bad step / stage / micro-batch / phase ----------------

    message = _refuses(model.ModelError, "a slot with step 0",
                       lambda: s.bubble((S(0, 0, 0, "f"),) + base[1:], 2))
    assert "step" in message, (
        "the refusal of step=0 does not name it: %r" % (message,))
    message = _refuses(model.ModelError, "a slot naming stage 2 of 2",
                       lambda: s.bubble((S(1, 2, 0, "f"),) + base[1:], 2))
    assert "names stage" in message, (
        "the refusal of an out-of-range stage does not name it: %r" % (message,))
    message = _refuses(model.ModelError, "a slot naming micro_batch 2 of 2",
                       lambda: s.bubble_fraction(
                           2, 2, schedule=(S(1, 0, 2, "f"),) + base[1:]))
    assert "names micro_batch" in message, (
        "the refusal of an out-of-range micro-batch does not name it: %r" % (message,))
    message = _refuses(model.ModelError, "a slot with phase 'x'",
                       lambda: s.bubble((S(1, 0, 0, "x"),) + base[1:], 2))
    assert "phase" in message, (
        "the refusal of a bad phase does not name it: %r" % (message,))
    say("slot fields", "a bad step, stage, micro-batch or phase is refused")

    # ---- missing / duplicated tasks, and the pipeline's dependencies ---------

    message = _refuses(model.ModelError, "a schedule missing a task",
                       lambda: s.bubble(base[:-1], 2))
    assert "never runs" in message, (
        "the refusal of a missing task does not name it: %r" % (message,))
    message = _refuses(model.ModelError, "a schedule forwarding a micro-batch twice",
                       lambda: s.bubble(base + (S(1, 0, 0, "f"),), 2))
    assert "twice" in message, (
        "the refusal of a duplicated task does not name the repetition: %r" % (message,))
    _refuses(model.ModelError, "replay of a schedule missing a task",
             lambda: s.replay(base[:-1], 2, 2))
    _refuses(model.ModelError, "bubble_fraction of a schedule missing a task",
             lambda: s.bubble_fraction(2, 2, schedule=base[:-1]))

    def _moved(where, to):
        return tuple(S(to if (x.micro_batch, x.stage, x.phase) == where else x.step,
                      x.stage, x.micro_batch, x.phase) for x in base)

    message = _refuses(model.ModelError, "a backward at its own forward's step",
                       lambda: s.bubble(
                           _moved((0, 0, "b"), 1), 2))
    assert "forward" in message, (
        "the refusal of a backward at or before its forward does not name it: %r"
        % (message,))
    message = _refuses(model.ModelError, "a forward not after the previous stage's",
                       lambda: s.bubble(_moved((0, 1, "f"), 1), 2))
    assert "forward" in message, (
        "the refusal of a forward out of order does not name it: %r" % (message,))
    message = _refuses(model.ModelError, "a backward not after the next stage's",
                       lambda: s.bubble(_moved((0, 0, "b"), 3), 2))
    assert "backward" in message, (
        "the refusal of a backward out of order does not name it: %r" % (message,))
    message = _refuses(model.ModelError, "two forwards in one step of one stage",
                       lambda: s.bubble(_moved((1, 0, "f"), 1), 2))
    assert "forward" in message, (
        "the refusal of two same-phase tasks does not name the phase: %r" % (message,))
    say("dependencies", "a missing/duplicated task and every broken dependency is refused")

    print("check_06: pipeline parallel — gpipe and one_f_one_b are canonical "
          "schedules with the forward stream mu+s+1, the bubble replayed from "
          "the (stage, step) pairs (24/88 for GPipe and 12/60 for 1F1B at (4, 8), "
          "3/11 and 1/5 exact), the exit steps descending then ascending, and "
          "every malformed schedule refused naming the offender")

# --- stage 7 -----------------------------------------------------------------------
def check_7():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("H1_REPO"), start, os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "distributed-training-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set H1_REPO=/path/to/learn-stuff-from-scratch")

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

    def _bubble(schedule, p):
        """The bubble and its exact fraction, from the slots alone: the makespan,
        the occupied `(stage, step)` pairs, what is left, and the reduced pair."""
        from math import gcd

        makespan = max(slot.step for slot in schedule)
        occupied = {(slot.stage, slot.step) for slot in schedule}
        total = p * makespan
        idle = total - len(occupied)
        divisor = gcd(idle, total) or 1
        return idle, (idle // divisor, total // divisor), makespan

    import dataclasses

    import model
    import stage_06 as s6
    import stage_07 as s

    # ---- the shape of the schedule data -------------------------------------

    assert s.PHASES == ("f", "b"), (
        "PHASES is %r, not the two phases a slot carries" % (s.PHASES,))
    assert [field.name for field in dataclasses.fields(s.Slot)] == [
        "step", "stage", "micro_batch", "phase", "chunk"], (
        "Slot's fields are %r, not the stage 6 shape plus (chunk)"
        % ([field.name for field in dataclasses.fields(s.Slot)],))
    assert getattr(s.Slot, "__dataclass_params__").frozen, (
        "Slot is not frozen: a schedule is frozen data")

    tiny = model.SHAPES["tiny"]
    p, m, v = 4, 8, 2

    # ---- the interleaving: GPipe over the m*v units -------------------------

    schedule = s.interleaved(p, m, v)
    assert isinstance(schedule, tuple) and all(
        isinstance(slot, s.Slot) for slot in schedule), (
        "interleaved returned %r, not a tuple of Slots" % (schedule,))
    assert schedule == tuple(sorted(
        schedule, key=lambda x: (x.step, x.stage, x.phase, x.micro_batch,
                                 x.chunk))), (
        "interleaved is not canonical: it must be sorted by "
        "(step, stage, phase, micro_batch, chunk)")
    assert schedule == s.interleaved(p, m, v), (
        "two calls with equal arguments returned unequal schedules: a schedule "
        "is a function of its inputs")
    assert len(schedule) == 2 * m * v * p, (
        "interleaved(4, 8, 2) has %d slots, not 2*m*v*p = %d"
        % (len(schedule), 2 * m * v * p))
    assert {slot.chunk for slot in schedule} == set(range(v)), (
        "the chunks are %r, not 0..%d"
        % (sorted({slot.chunk for slot in schedule}), v - 1))
    assert {slot.stage for slot in schedule} == set(range(p)), (
        "the stages are %r, not 0..%d"
        % (sorted({slot.stage for slot in schedule}), p - 1))
    assert {slot.micro_batch for slot in schedule} == set(range(m)), (
        "the micro-batches are %r, not 0..%d"
        % (sorted({slot.micro_batch for slot in schedule}), m - 1))

    slots = {(slot.micro_batch, slot.chunk, slot.stage, slot.phase): slot
             for slot in schedule}
    assert len(slots) == len(schedule), (
        "interleaved repeats an (micro_batch, chunk, stage, phase)")

    # THE FORWARD AND THE BACKWARD STREAMS, fixed by the template: unit
    # w = mu*v + chunk forwards at stage s at step w + s + 1 and backwards at
    # 2*(m*v) + 2*p - 2 - w - s.
    for mu in range(m):
        for chunk in range(v):
            unit = mu * v + chunk
            for stage in range(p):
                for phase, want in (
                        ("f", unit + stage + 1),
                        ("b", 2 * m * v + 2 * p - 2 - unit - stage)):
                    key = (mu, chunk, stage, phase)
                    assert key in slots, (
                        "micro-batch %d never runs its %r of chunk %d through "
                        "stage %d" % (mu, phase, chunk, stage))
                    got = slots[key].step
                    assert got == want, (
                        "micro-batch %d's %r of chunk %d through stage %d is at "
                        "step %d, not %d: the unit w = mu*v + chunk fixes the "
                        "streams" % (mu, phase, chunk, stage, got, want))

    # a step of a stage carries at most one forward and one backward, and never
    # a backward in the step of its own unit's forward.
    for stage in range(p):
        for step in {slot.step for slot in schedule if slot.stage == stage}:
            at = [slot for slot in schedule
                  if slot.stage == stage and slot.step == step]
            assert len(at) <= 2 and (len(at) == 1
                                     or at[0].phase != at[1].phase), (
                "stage %d carries %r in step %d; a step of a stage is one "
                "forward, one backward, or both" % (stage, at, step))
    for mu in range(m):
        for chunk in range(v):
            for stage in range(p):
                assert slots[(mu, chunk, stage, "f")].step < \
                    slots[(mu, chunk, stage, "b")].step, (
                    "micro-batch %d's backward of chunk %d through stage %d is "
                    "not after its own forward there" % (mu, chunk, stage))

    # the last unit's forward leaves the last stage to close the pipeline.
    assert slots[(m - 1, v - 1, p - 1, "f")].step == m * v + p - 1, (
        "the last unit's forward clears the last stage at step %d, not "
        "m*v + p - 1 = %d"
        % (slots[(m - 1, v - 1, p - 1, "f")].step, m * v + p - 1))

    # ---- v = 1 is stage 6's gpipe, exactly ----------------------------------

    for stages, micro_batches in ((4, 8), (2, 3)):
        one = s.interleaved(stages, micro_batches, 1)
        assert all(slot.chunk == 0 for slot in one), (
            "interleaved(%d, %d, 1) carries a non-zero chunk: %r"
            % (stages, micro_batches,
               sorted({slot.chunk for slot in one})))
        plain = [(slot.step, slot.stage, slot.micro_batch, slot.phase)
                 for slot in one]
        want = [(slot.step, slot.stage, slot.micro_batch, slot.phase)
                for slot in s6.gpipe(stages, micro_batches)]
        assert plain == want, (
            "interleaved(%d, %d, 1) is not stage 6's gpipe(%d, %d): %r against "
            "%r" % (stages, micro_batches, stages, micro_batches, plain, want))

    # ---- the bubble, by replaying the slots ---------------------------------

    idle, fraction, makespan = _bubble(schedule, p)
    assert makespan == 2 * m * v + 2 * p - 2, (
        "interleaved(4, 8, 2) makespan is %d steps, not 2*m*v + 2*p - 2 = %d"
        % (makespan, 2 * m * v + 2 * p - 2))
    assert idle == 24, (
        "interleaved(4, 8, 2) idles %d (stage, step) pairs, not 24: the bubble "
        "is read off the slots, and it is the same 24 stage 6 idles for "
        "(4, 8) over a longer makespan" % (idle,))
    assert fraction == (3, 19), (
        "interleaved(4, 8, 2)'s bubble fraction is %r, not the exact pair "
        "(3, 19)" % (fraction,))
    for stages, micro_batches, chunks in ((4, 8, 2), (2, 3, 2), (4, 8, 1)):
        other = s.interleaved(stages, micro_batches, chunks)
        got = _bubble(other, stages)[1]
        want = s6.bubble_fraction(stages, micro_batches * chunks,
                                  schedule=s6.gpipe(stages,
                                                    micro_batches * chunks))
        assert got == want, (
            "interleaved(%d, %d, %d)'s bubble is %r, but stage 6's GPipe over "
            "m*v = %d micro-batches gives %r: the interleaving is GPipe "
            "relabeled and nothing else"
            % (stages, micro_batches, chunks, got,
               micro_batches * chunks, want))
    assert _bubble(s.interleaved(1, 4, 3), 1)[1] == (0, 1), (
        "a pipeline of one stage has a bubble: it must be 0/1")
    assert _bubble(s.interleaved(2, 3, 2), 2)[1] == (1, 7), (
        "interleaved(2, 3, 2)'s bubble is %r, not (1, 7)"
        % (_bubble(s.interleaved(2, 3, 2), 2)[1],))

    # ---- the lifetimes ------------------------------------------------------

    intervals = s.lifetime(schedule)
    assert isinstance(intervals, tuple) and len(intervals) == m * v * p, (
        "lifetime(4, 8, 2) returned %d intervals, not m*v*p = %d"
        % (len(intervals), m * v * p))
    want = [(slots[(mu, chunk, stage, "f")].step,
             slots[(mu, chunk, stage, "b")].step)
            for mu in range(m) for chunk in range(v) for stage in range(p)]
    assert list(intervals) == want, (
        "lifetime is not one (birth, death) per forward in (micro_batch, chunk, "
        "stage) order, born at the forward and dead at the same unit's backward")
    for birth, death in intervals:
        assert birth < death, (
            "an activation is born at %d and dead at %d: an activation does not "
            "die before it is born" % (birth, death))

    # a rank's chunk buffer is handed on the step after the forward produces it,
    # so the hand-off intervals of one buffer never overlap: no buffer is reused
    # while an activation is still in flight.
    by_buffer = {}
    for mu in range(m):
        for chunk in range(v):
            for stage in range(p):
                birth = slots[(mu, chunk, stage, "f")].step
                by_buffer.setdefault((stage, chunk), []).append((birth, birth + 1))
    for buffer, spans in by_buffer.items():
        spans.sort()
        for index in range(1, len(spans)):
            assert spans[index][0] >= spans[index - 1][1], (
                "buffer %r holds two activations at once: %r and %r"
                % (buffer, spans[index - 1], spans[index]))

    # the peak is the UNION of the intervals, not the longest one.
    steps = max(death for _, death in intervals)
    peak = max(sum(1 for birth, death in intervals if birth <= step <= death)
               for step in range(1, steps + 1))
    assert peak > 1, (
        "the peak is %d activations: a pipeline deeper than one activation is "
        "the whole point" % (peak,))
    assert s.in_flight(schedule, tiny, batch=1, seq=1) == \
        peak * tiny.activation_bytes(1, 1), (
        "in_flight(4, 8, 2) is %d, not %d x %d activation bytes: the peak is "
        "the number of live intervals, never the longest one"
        % (s.in_flight(schedule, tiny, batch=1, seq=1), peak,
           tiny.activation_bytes(1, 1)))
    assert s.in_flight(schedule, tiny, batch=2, seq=1) == \
        2 * s.in_flight(schedule, tiny, batch=1, seq=1), (
        "in_flight does not scale with the batch: it is a count of activations "
        "times their bytes, and an activation grows with the batch")
    assert s.in_flight(schedule, tiny, batch=1, seq=3) > \
        s.in_flight(schedule, tiny, batch=1, seq=1), (
        "in_flight does not grow with the sequence length")


    # ---- the refusals -------------------------------------------------------

    for bad_p in (0, -1, True, "4"):
        message = _refuses(model.ModelError, "a p that is not a positive count",
                           lambda bad_p=bad_p: s.interleaved(bad_p, 8, 2))
        assert "p" in message, (
            "the refusal of p=%r does not name it: %r" % (bad_p, message))
    for bad_m in (0, False, 8.0):
        message = _refuses(model.ModelError, "an m that is not a positive count",
                           lambda bad_m=bad_m: s.interleaved(4, bad_m, 2))
        assert "m" in message, (
            "the refusal of m=%r does not name it: %r" % (bad_m, message))
    for bad_v in (0, 2.5, "2"):
        message = _refuses(model.ModelError, "a v that is not a positive count",
                           lambda bad_v=bad_v: s.interleaved(4, 8, bad_v))
        assert "v" in message, (
            "the refusal of v=%r does not name it: %r" % (bad_v, message))

    _refuses(model.ModelError, "a schedule that is not a tuple",
             lambda: s.lifetime(list(schedule)))
    _refuses(model.ModelError, "a schedule that is not a tuple of Slots",
             lambda: s.lifetime(("not a slot",)))
    _refuses(model.ModelError, "an empty schedule", lambda: s.lifetime(()))
    _refuses(model.ModelError, "a schedule missing a (micro_batch, chunk, "
                               "stage, phase)",
             lambda: s.lifetime(schedule[:-1]))

    def _relabel(edits):
        return tuple(s.Slot(edits.get((slot.micro_batch, slot.chunk, slot.stage,
                                       slot.phase), slot.step),
                            slot.stage, slot.micro_batch, slot.phase, slot.chunk)
                     for slot in schedule)

    _refuses(model.ModelError, "a backward at or before its own forward",
             lambda: s.lifetime(_relabel(
                 {(0, 0, 3, "b"): 1})))
    _refuses(model.ModelError, "a chunk order that breaks the dependency",
             lambda: s.lifetime(tuple(
                 s.Slot(slot.step, slot.stage, slot.micro_batch, slot.phase,
                        1 - slot.chunk if slot.micro_batch == 0 else slot.chunk)
                 for slot in schedule)))
    _refuses(model.ModelError, "a forward that overtakes its previous stage",
             lambda: s.lifetime(_relabel(
                 {(0, 0, 1, "f"): 1})))
    _refuses(model.ModelError, "a backward that overtakes the next stage's",
             lambda: s.lifetime(_relabel(
                 {(0, 0, 1, "b"): 40})))
    _refuses(model.ModelError, "two tasks of one phase in one step of one stage",
             lambda: s.lifetime(_relabel(
                 {(2, 0, 0, "f"): 1})))
    _refuses(model.ModelError, "units that do not divide evenly over the chunks",
             lambda: s.lifetime(tuple(
                 slot for slot in schedule
                 if (slot.micro_batch, slot.chunk) != (m - 1, v - 1))))

    message = _refuses(model.ModelError, "a shape that is not a ModelShape",
                       lambda: s.in_flight(schedule, 4, batch=1, seq=1))
    assert "shape" in message, (
        "the refusal of a bad shape does not name it: %r" % (message,))
    message = _refuses(model.ModelError, "a batch that is not a positive count",
                       lambda: s.in_flight(schedule, tiny, batch=0, seq=1))
    assert "batch" in message, (
        "the refusal of a bad batch does not name it: %r" % (message,))
    message = _refuses(model.ModelError, "a bool seq",
                       lambda: s.in_flight(schedule, tiny, batch=1, seq=True))
    assert "seq" in message, (
        "the refusal of a bad seq does not name it: %r" % (message,))

    print("check_07: pipeline schedules — the interleaving is stage 6's GPipe "
          "over m*v units and its bubble replays to 3/19 at (4, 8, 2), v = 1 is "
          "gpipe exactly, an activation's lifetime is its forward-to-backward "
          "range, the peak is the union of those ranges times one activation's "
          "bytes, and a schedule whose units do not divide evenly over its "
          "chunks is refused")

# --- stage 8 -----------------------------------------------------------------------
def check_8():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("H1_REPO"), start, os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "distributed-training-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set H1_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call):
        """The message of the refusal `call` must raise, or the mistake named.

        A return, or any other exception, is the mistake `what` names; a stub's
        `NotImplementedError` is never one of them and is re-raised untouched.
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

    def _sends(table):
        """Each rank's dispatched placements: its row, its own piece taken out."""
        return tuple(sum(row) - row[index] for index, row in enumerate(table))

    def _takes(table):
        """Each rank's intake: its column, its own piece taken out."""
        size = len(table)
        return tuple(sum(table[other][index] for other in range(size)) - table[index][index]
                     for index in range(size))

    def _busiest(splits):
        """The busiest rank's share in one direction — the maximum, not the mean."""
        return max(max(_sends(splits)), max(_takes(splits)))

    def _kept(table, capacity):
        """The routing table with every cell capped at `capacity` placements."""
        return tuple(tuple(min(cell, capacity) for cell in row) for row in table)

    def _transpose(table):
        """The combine's table: what expert rank `j` returns to source rank `i`."""
        size = len(table)
        return tuple(tuple(table[source][expert] for source in range(size))
                     for expert in range(size))

    def _moved(fabric_plan):
        """The elements a built plan actually crosses the fabric with."""
        return sum(transfer.length for transfer in fabric_plan.transfers)

    def _capacity(table, capacity_factor):
        """The cap one cell keeps: `factor` times the table's mean cell, ceiled."""
        placed = sum(sum(row) for row in table)
        size = len(table)
        return -(-capacity_factor * placed // (size * size))

    import fabric
    import model
    import plans

    import stage_01 as s1
    import stage_08 as s8

    # ---- the fixtures ------------------------------------------------------
    moe2 = model.ModelShape(layers=2, hidden=128, heads=4, ffn_hidden=256,
                            vocab=12, experts=2, top_k=1)
    moe2k2 = model.ModelShape(layers=2, hidden=128, heads=4, ffn_hidden=256,
                              vocab=12, experts=2, top_k=2)
    moe4 = model.ModelShape(layers=2, hidden=8, heads=2, ffn_hidden=16,
                            vocab=12, experts=4, top_k=2)
    moe4k1 = model.ModelShape(layers=2, hidden=8, heads=2, ffn_hidden=16,
                             vocab=12, experts=4, top_k=1)
    moe1 = model.ModelShape(layers=2, hidden=8, heads=2, ffn_hidden=16,
                            vocab=12, experts=1, top_k=1)
    world1, world2, world4 = fabric.full(1), fabric.full(2), fabric.full(4)

    # ---- routing: the table, token by token --------------------------------

    balanced2 = s8.routing(moe2, batch=2, seq=4)
    assert balanced2 == ((4, 4), (4, 4)), (
        "the routing of eight top-1 tokens over two experts is %r, not "
        "((4, 4), (4, 4)): a row is one source rank's placements per expert"
        % (balanced2,))
    assert isinstance(balanced2, tuple) and all(isinstance(row, tuple) for row in balanced2), (
        "the routing is %r: the table is a tuple of rows, not a %s"
        % (balanced2, type(balanced2).__name__))

    hot2 = s8.routing(moe2, batch=2, seq=4, hot=0)
    assert hot2 == ((8, 0), (8, 0)), (
        "the hot routing of eight top-1 tokens on expert 0 is %r, not "
        "((8, 0), (8, 0)): every token's last choice moves to the hot expert"
        % (hot2,))

    balanced4 = s8.routing(moe4, batch=2, seq=4)
    assert balanced4 == ((4, 4, 4, 4),) * 4, (
        "the routing of eight top-2 tokens over four experts is %r, not "
        "((4, 4, 4, 4),) * 4" % (balanced4,))
    hot4 = s8.routing(moe4, batch=2, seq=4, hot=0)
    assert hot4 == ((8, 4, 2, 2),) * 4, (
        "the hot routing of eight top-2 tokens on expert 0 is %r, not "
        "((8, 4, 2, 2),) * 4: the hot expert takes every token's last choice, "
        "and the token it already had stays" % (hot4,))
    hot4k1 = s8.routing(moe4k1, batch=2, seq=4, hot=0)
    assert hot4k1 == ((8, 0, 0, 0),) * 4, (
        "the hot routing of eight top-1 tokens on four experts is %r, not "
        "((8, 0, 0, 0),) * 4" % (hot4k1,))

    top2_totals = sum(sum(row) for row in balanced4)
    assert top2_totals == 64, (
        "the eight top-2 tokens place %r placements, not 64: top_k is counted "
        "per token, and eight tokens reach two experts each over four sources"
        % (top2_totals,))
    assert top2_totals == 2 * sum(sum(row) for row in s8.routing(
        moe4k1, batch=2, seq=4)), (
        "top_k = 2 places %r placements, not twice the top_k = 1 count: a "
        "router that places the choices once has counted top_k once"
        % (top2_totals,))
    assert sum(sum(row) for row in balanced2) == 16, (
        "the eight top-1 tokens place %r placements, not 16: every token "
        "reaches exactly one expert" % (sum(sum(row) for row in balanced2),))

    even_k2 = s8.routing(moe2k2, batch=2, seq=4)
    assert even_k2 == ((8, 8), (8, 8)) and s8.routing(
        moe2k2, batch=2, seq=4, hot=0) == ((8, 8), (8, 8)), (
        "with top_k = experts every token already reaches every expert, so the "
        "routing is %r whether or not an expert is hot: a router that sends "
        "every token to every expert is what top_k = 1 must not do"
        % (even_k2,))

    six = s8.routing(moe4, batch=2, seq=3)
    assert six == ((3, 4, 3, 2),) * 4, (
        "six top-2 tokens over four experts route %r, not ((3, 4, 3, 2),) * 4: "
        "the choices are (q + k) % experts, per token" % (six,))

    hot_one = s8.routing(moe4, batch=2, seq=4, hot=1)
    assert hot_one == ((2, 8, 4, 2),) * 4, (
        "with hot=1 the routing is %r, not ((2, 8, 4, 2),) * 4: the hot expert "
        "is the one the caller names, and only the token's last choice moves to "
        "it" % (hot_one,))
    hot_three = s8.routing(moe4, batch=2, seq=4, hot=3)
    assert hot_three == ((4, 2, 2, 8),) * 4, (
        "with hot=3 the routing is %r, not ((4, 2, 2, 8),) * 4: a routing that "
        "always makes expert 0 hot ignores the hot expert it was given"
        % (hot_three,))
    assert s8.balance_loss(hot_one) == s8.balance_loss(hot_three) == 1536, (
        "the hot=1 and hot=3 tables lose %r and %r, not the same 1536: which "
        "expert is hot does not change how unbalanced the table is"
        % (s8.balance_loss(hot_one), s8.balance_loss(hot_three)))

    assert s8.routing(moe2, batch=2, seq=4) == balanced2, (
        "two identical routing calls returned different tables: the routing is "
        "a function of its inputs")

    message = _refuses(model.ModelError, "a dense shape",
                       lambda: s8.routing(model.SHAPES["tiny"], batch=2, seq=4))
    assert "experts" in message, (
        "the refusal of a dense shape does not name experts: %r" % (message,))
    message = _refuses(model.ModelError, "a hot expert that is not an expert",
                       lambda: s8.routing(moe2, batch=2, seq=4, hot=2))
    assert "hot" in message, (
        "the refusal of an out-of-range hot expert does not name hot: %r"
        % (message,))
    message = _refuses(model.ModelError, "a negative hot expert",
                       lambda: s8.routing(moe2, batch=2, seq=4, hot=-1))
    assert "hot" in message, (
        "the refusal of hot=-1 does not name hot: %r" % (message,))
    message = _refuses(model.ModelError, "a bool batch",
                       lambda: s8.routing(moe2, batch=True, seq=4))
    assert "batch" in message, (
        "the refusal of batch=True does not name batch: %r" % (message,))
    message = _refuses(model.ModelError, "a sequence of zero",
                       lambda: s8.routing(moe2, batch=2, seq=0))
    assert "seq" in message, (
        "the refusal of seq=0 does not name seq: %r" % (message,))
    message = _refuses(model.ModelError, "a shape that is not a ModelShape",
                       lambda: s8.routing(42, batch=2, seq=4))
    assert "shape" in message, (
        "the refusal of a shape that is not a ModelShape does not name shape: "
        "%r" % (message,))

    # ---- dropped: the cap's count ------------------------------------------

    assert s8.dropped(balanced2, 1) == 0 and s8.dropped(balanced2, 2) == 0, (
        "a balanced table drops %r then %r placements, not nothing: its cells "
        "are the mean cell, and the cap is a multiple of it"
        % (s8.dropped(balanced2, 1), s8.dropped(balanced2, 2)))
    assert s8.dropped(hot2, 1) == 8, (
        "the hot table drops %r placements at capacity_factor 1, not 8: the cap "
        "is ceil(1 * 16 / 4) = 4, and each of the two rows has an 8-placement "
        "cell" % (s8.dropped(hot2, 1),))
    assert s8.dropped(hot2, 2) == 0, (
        "the hot table drops %r placements at capacity_factor 2, not nothing: "
        "the capacity_factor is part of the cap, which becomes 8"
        % (s8.dropped(hot2, 2),))
    assert s8.dropped(hot4, 1) == 16 and s8.dropped(hot4, 2) == 0, (
        "the four-rank hot table drops %r then %r placements, not 16 then "
        "nothing: the cap is ceil(factor * 64 / 16) = 4 * factor"
        % (s8.dropped(hot4, 1), s8.dropped(hot4, 2)))
    assert s8.dropped(balanced4, 1) == 0, (
        "the balanced four-rank table drops %r placements, not nothing"
        % (s8.dropped(balanced4, 1),))
    assert s8.dropped(((2, 2, 1, 1),) * 4, 1) == 0, (
        "the six-token top-1 table drops %r placements, not nothing: its total "
        "is 24, the cap is ceil(24 / 16) = 2, and its cells are at most 2"
        % (s8.dropped(((2, 2, 1, 1),) * 4, 1),))
    assert s8.dropped(s8.routing(moe4, batch=2, seq=3, hot=0), 1) == 16, (
        "the six-token hot table drops %r placements, not 16: its rows are "
        "(6, 4, 1, 1) and the cap is ceil(48 / 16) = 3, so a 6-cell and a 4-cell "
        "each lose their excess in all four rows"
        % (s8.dropped(s8.routing(moe4, batch=2, seq=3, hot=0), 1),))
    assert isinstance(s8.dropped(hot2, 1), int) and not isinstance(
        s8.dropped(hot2, 1), bool), (
        "dropped returns a %s, not an int count"
        % (type(s8.dropped(hot2, 1)).__name__,))

    message = _refuses(model.ModelError, "a ragged table",
                       lambda: s8.dropped(((1, 2), (1,)), 1))
    assert "routing" in message, (
        "the refusal of a ragged table does not name routing: %r" % (message,))
    message = _refuses(model.ModelError, "an empty table",
                       lambda: s8.dropped((), 1))
    assert "routing" in message, (
        "the refusal of an empty table does not name routing: %r" % (message,))
    message = _refuses(model.ModelError, "a negative placement count",
                       lambda: s8.dropped(((1, -2), (1, 1)), 1))
    assert "routing" in message, (
        "the refusal of a negative placement count does not name routing: %r"
        % (message,))
    message = _refuses(model.ModelError, "a capacity_factor of zero",
                       lambda: s8.dropped(balanced2, 0))
    assert "capacity_factor" in message, (
        "the refusal of capacity_factor=0 does not name capacity_factor: %r"
        % (message,))
    message = _refuses(model.ModelError, "a bool capacity_factor",
                       lambda: s8.dropped(balanced2, True))
    assert "capacity_factor" in message, (
        "the refusal of capacity_factor=True does not name capacity_factor: %r"
        % (message,))

    # ---- balance_loss: the integer statistic -------------------------------

    assert s8.balance_loss(balanced2) == 0 and s8.balance_loss(balanced4) == 0, (
        "a balanced table's loss is %r and %r, not nothing: every expert holds "
        "the same load" % (s8.balance_loss(balanced2), s8.balance_loss(balanced4)))
    assert s8.balance_loss(even_k2) == 0, (
        "top_k = experts loads every expert equally, so its loss is %r, not 0"
        % (s8.balance_loss(even_k2),))
    assert s8.balance_loss(hot2) == 256, (
        "the two-rank hot table's loss is %r, not 256: the loads are (16, 0), "
        "so experts * sum(load ** 2) - sum(load) ** 2 = 2 * 256 - 256"
        % (s8.balance_loss(hot2),))
    assert s8.balance_loss(hot4) == 1536, (
        "the four-rank hot table's loss is %r, not 1536: the loads are "
        "(32, 16, 8, 8)" % (s8.balance_loss(hot4),))
    assert s8.balance_loss(six) == 128, (
        "the six-token table's loss is %r, not 128: its loads are (12, 16, 12, "
        "8), which no even split reaches" % (s8.balance_loss(six),))
    assert s8.balance_loss(((2, 2, 1, 1),) * 4) == 64, (
        "the six-token top-1 table's loss is %r, not 64: its loads are "
        "(8, 8, 4, 4)" % (s8.balance_loss(((2, 2, 1, 1),) * 4),))

    hand = ((1, 0, 0, 0), (0, 2, 0, 0), (3, 0, 0, 0), (0, 0, 0, 4))
    assert s8.balance_loss(hand) == 44, (
        "the hand table's loss is %r, not 44: its expert loads are (4, 2, 0, "
        "4) -> 4 * 36 - 100, which is a sum of squared deviations from the "
        "mean (2.5) and not a max-minus-mean" % (s8.balance_loss(hand),))
    assert s8.balance_loss(hand[1:] + hand[:1]) == 44, (
        "rotating the table's rows changed the loss to %r: the loss reads the "
        "experts' loads — the columns — not the rows"
        % (s8.balance_loss(hand[1:] + hand[:1]),))
    assert isinstance(s8.balance_loss(hot2), int) and not isinstance(
        s8.balance_loss(hot2), bool), (
        "balance_loss returns a %s, not an int" % (type(s8.balance_loss(hot2)).__name__,))
    message = _refuses(model.ModelError, "a ragged table",
                       lambda: s8.balance_loss(((4, 4), (4,))))
    assert "routing" in message, (
        "the refusal of a ragged table does not name routing: %r" % (message,))
    message = _refuses(model.ModelError, "an empty table",
                       lambda: s8.balance_loss(()))
    assert "routing" in message, (
        "the refusal of an empty table does not name routing: %r" % (message,))

    # ---- expert_parallel: the two exchanges --------------------------------

    balanced = s8.expert_parallel(moe2, world2, batch=2, seq=4)
    hot = s8.expert_parallel(moe2, world2, batch=2, seq=4, hot=0)
    hot_capped = s8.expert_parallel(moe2, world2, batch=2, seq=4, hot=0,
                                    capacity_factor=1)
    balanced_capped = s8.expert_parallel(moe2, world2, batch=2, seq=4,
                                         capacity_factor=1)
    four_way = s8.expert_parallel(moe4, world4, batch=2, seq=4)
    hot_east = s8.expert_parallel(moe4k1, world4, batch=2, seq=4, hot=0)
    deep_k2 = s8.expert_parallel(moe2k2, world2, batch=2, seq=4)
    alone = s8.expert_parallel(moe1, world1, batch=2, seq=4)

    for name, plan, world in (("the balanced plan", balanced, world2),
                              ("the hot plan", hot, world2),
                              ("the capped hot plan", hot_capped, world2),
                              ("the four-rank plan", four_way, world4),
                              ("the one-rank plan", alone, world1)):
        assert [collective.name for collective in plan.collectives] == [
            "dispatch", "combine"], (
            "%s issues %r, not the dispatch and the combine in that order: one "
            "exchange cannot both deliver the token and bring its output home"
            % (name, [collective.name for collective in plan.collectives]))
        assert [collective.axis for collective in plan.collectives] == ["ep", "ep"], (
            "%s runs its exchanges on %r, not the ep axis"
            % (name, [collective.axis for collective in plan.collectives]))
        assert [collective.algo for collective in plan.collectives] == [
            "alltoall", "alltoall"], (
            "%s labels its exchanges %r, not alltoall"
            % (name, [collective.algo for collective in plan.collectives]))
        assert [collective.group for collective in plan.collectives] == [
            world.ranks, world.ranks], (
            "%s runs over %r, not the world's own ranks %r"
            % (name, [collective.group for collective in plan.collectives],
               world.ranks))
        for collective in plan.collectives:
            problems = fabric.legality_problems(world, collective.plan)
            assert problems == (), (
                "%s's %s plan is not legal on %s: %r"
                % (name, collective.name, world, problems))

    assert [collective.length for collective in balanced.collectives] == [512, 512], (
        "the balanced plan's lengths are %r, not [512, 512]: eight of sixteen "
        "placements per rank cross, at 128 elements of hidden each"
        % ([collective.length for collective in balanced.collectives],))
    assert [collective.length for collective in hot.collectives] == [1024, 1024], (
        "the hot plan's lengths are %r, not [1024, 1024]: one rank dispatches "
        "its whole block"
        % ([collective.length for collective in hot.collectives],))
    assert [collective.length for collective in hot_capped.collectives] == [1024, 512], (
        "the capped hot plan's lengths are %r, not [1024, 512]: the dispatch "
        "carries every placement, the combine only the capped ones"
        % ([collective.length for collective in hot_capped.collectives],))
    assert [collective.length for collective in balanced_capped.collectives] == [512, 512], (
        "the capped balanced plan's lengths are %r, not [512, 512]: nothing is "
        "over the cap" % ([collective.length for collective in balanced_capped.collectives],))
    assert [collective.length for collective in four_way.collectives] == [96, 96], (
        "the four-rank balanced plan's lengths are %r, not [96, 96]: twelve of "
        "sixteen placements per rank cross, at 8 elements of hidden each"
        % ([collective.length for collective in four_way.collectives],))
    assert [collective.length for collective in hot_east.collectives] == [192, 96], (
        "the four-rank hot plan's lengths are %r, not [192, 96]: the hot "
        "expert's rank takes in 24 placements while the others move 4"
        % ([collective.length for collective in hot_east.collectives],))
    assert [collective.length for collective in deep_k2.collectives] == [1024, 1024], (
        "top_k = 2 over two experts dispatches %r elements per rank, not the "
        "top_k = 1 plan's 512: both experts are reached by every token"
        % ([collective.length for collective in deep_k2.collectives],))
    assert [collective.length for collective in alone.collectives] == [0, 0], (
        "a group of one has lengths %r, not nothing: the piece the rank keeps "
        "never crosses the fabric"
        % ([collective.length for collective in alone.collectives],))

    # the exchange is priced by the busiest rank, not the mean of the senders
    mean_send = sum(_sends(((8, 0), (8, 0)))) // 2 * 128
    assert [collective.length for collective in hot.collectives][0] == 1024 != mean_send, (
        "the hot dispatch is priced %r elements per rank, not the mean of the "
        "sending ranks (%r): the layer waits for the rank with the most to "
        "hand over, not for the average of them"
        % ([collective.length for collective in hot.collectives][0], mean_send,))
    assert s1.plan_bytes(hot) == 8192 and s1.plan_bytes(balanced) == 4096, (
        "the hot and balanced plans put %r and %r bytes per rank on the wire, "
        "not 8192 and 4096: the two routings hold the same tokens, and only the "
        "busiest rank's share tells them apart"
        % (s1.plan_bytes(hot), s1.plan_bytes(balanced)))
    assert s1.step_ticks(world2, hot) == 92 != s1.step_ticks(world2, balanced), (
        "the hot plan costs %r ticks and the balanced %r: with the same token "
        "count they must differ, and a plan that charges the mean reports the "
        "balanced 52 for both" % (s1.step_ticks(world2, hot),
                                  s1.step_ticks(world2, balanced)))
    assert s1.step_ticks(world2, balanced) == 52, (
        "the balanced exchange costs %r ticks, not 26 + 26: the two collectives "
        "are summed, each a one-step exchange of 2048 bytes"
        % (s1.step_ticks(world2, balanced),))
    assert s1.plan_ticks(world2, hot.collectives[0].plan) == 46, (
        "the hot dispatch's one step costs %r ticks, not 5 + ceil(4096 / 100): "
        "it moves one 1024-element transfer" % (s1.plan_ticks(world2, hot.collectives[0].plan),))
    assert s1.step_ticks(world4, four_way) == 42, (
        "the four-rank balanced exchange costs %r ticks, not 21 + 21"
        % (s1.step_ticks(world4, four_way),))

    # the built plans are the ragged tables the routing names
    assert [len(collective.plan.transfers) for collective in balanced.collectives] == [2, 2], (
        "the balanced pair built %r transfers, not the two off-diagonal cells "
        "of a 2x2 table: the local piece never moves"
        % ([len(collective.plan.transfers) for collective in balanced.collectives],))
    assert [len(collective.plan.transfers) for collective in hot.collectives] == [1, 1], (
        "the hot pair built %r transfers, not one each: one rank dispatches "
        "its whole block and the other keeps its own"
        % ([len(collective.plan.transfers) for collective in hot.collectives],))
    assert [len(collective.plan.steps()) for collective in balanced.collectives] == [1, 1], (
        "the balanced exchange takes %r steps on a clique of two, not the one "
        "step full(2) admits"
        % ([len(collective.plan.steps()) for collective in balanced.collectives],))
    assert [len(collective.plan.transfers) for collective in four_way.collectives] == [12, 12], (
        "the four-rank pair built %r transfers, not twelve each: every ordered "
        "pair of distinct ranks sends its own piece"
        % ([len(collective.plan.transfers) for collective in four_way.collectives],))

    dispatch_moved = _moved(hot_capped.collectives[0].plan)
    combine_moved = _moved(hot_capped.collectives[1].plan)
    cap = _capacity(hot2, 1)
    wanted = (sum(sum(row) for row in hot2)
              - sum(hot2[index][index] for index in range(2))) * 128
    capped_drop = sum(max(0, hot2[source][expert] - cap)
                      for source in range(2) for expert in range(2)
                      if source != expert) * 128
    assert dispatch_moved == wanted == 1024, (
        "the dispatch moves %r elements, not the %r the table's off-diagonal "
        "placements come to: the rank hands over every placement the routing "
        "names — capped or not — and the piece it keeps never moves"
        % (dispatch_moved, wanted))
    assert dispatch_moved - combine_moved == capped_drop == 512, (
        "the dispatch moves %r elements and the combine %r, a difference of "
        "%r, not the %r the capped-off-diagonal placements come to: a cap that "
        "never reaches the plan leaves the two exchanges equal"
        % (dispatch_moved, combine_moved, dispatch_moved - combine_moved,
           capped_drop))
    assert s8.dropped(hot2, 1) * 128 >= capped_drop, (
        "the count of dropped placements (%r) is below what the exchange stops "
        "moving (%r): the diagonal cell's own excess is dropped but never "
        "moved, so the count is never the smaller" % (s8.dropped(hot2, 1) * 128,
                                                       capped_drop))

    # the combine runs back towards the token owners, not the same way as out
    out_links = {(t.src, t.dst) for t in hot_capped.collectives[0].plan.transfers}
    back_links = {(t.src, t.dst) for t in hot_capped.collectives[1].plan.transfers}
    assert ("r1", "r0") in out_links and ("r0", "r1") in back_links, (
        "the dispatch's links are %r and the combine's %r: the combine is the "
        "transposed table — the expert's rank returns what it kept to the "
        "owner, it does not run the dispatch again" % (out_links, back_links))

    # the two ragged tables the check recomputes from the routing itself
    recomputed = _busiest(tuple(tuple(cell * 128 for cell in row)
                                for row in _kept(hot2, _capacity(hot2, 1))))
    assert [collective.length for collective in hot_capped.collectives] == [
        1024, recomputed], (
        "the capped hot combine's length is %r, not the %r the capped table's "
        "busiest rank moves" % ([collective.length for collective in hot_capped.collectives], recomputed,))

    assert hot.compute == 0 and balanced.compute == 0 and four_way.compute == 0, (
        "the exchange steps own %r, %r and %r ticks of compute, not none: no "
        "device enters this stage's surface, so the step prices what moves"
        % (hot.compute, balanced.compute, four_way.compute))

    # ---- the ledger --------------------------------------------------------

    assert balanced.memory == (
        s1.MemoryLine("expert_state", world2.ranks, 3145728),
        s1.MemoryLine("activations", world2.ranks, 4096),), (
        "the two-rank ledger is %r, not one expert's state (2 layers of "
        "3 * 256 * 128 parameters at 16 B) and the busiest intake (8 of 8 "
        "placements of 128 elements)" % (balanced.memory,))
    assert hot.memory == (
        s1.MemoryLine("expert_state", world2.ranks, 3145728),
        s1.MemoryLine("activations", world2.ranks, 8192),), (
        "the hot ledger is %r, not the same expert state and the 16-placement "
        "intake" % (hot.memory,))
    assert four_way.memory == (
        s1.MemoryLine("expert_state", world4.ranks, 12288),
        s1.MemoryLine("activations", world4.ranks, 512),), (
        "the four-rank ledger is %r, not one expert of 2 layers * 3 * 16 * 8 "
        "parameters at 16 B and an 8-placement intake of 8 elements"
        % (four_way.memory,))
    assert hot_east.memory[1] == s1.MemoryLine("activations", world4.ranks, 1024), (
        "the four-rank hot activation line is %r, not the hot expert's "
        "32-placement column" % (hot_east.memory[1],))

    # ---- the refusals and the one-rank group -------------------------------

    message = _refuses(model.ModelError, "a dense shape",
                       lambda: s8.expert_parallel(model.SHAPES["tiny"], world2,
                                                  batch=2, seq=4))
    assert "experts" in message, (
        "the refusal of a dense shape does not name experts: %r" % (message,))
    message = _refuses(model.ModelError, "a world that is not the expert count",
                       lambda: s8.expert_parallel(moe4, world2, batch=2, seq=4))
    assert "4" in message and "2" in message, (
        "the refusal of a two-rank world for four experts does not name both: "
        "%r" % (message,))
    message = _refuses(model.ModelError, "a capacity_factor of zero",
                       lambda: s8.expert_parallel(moe2, world2, batch=2, seq=4,
                                                  capacity_factor=0))
    assert "capacity_factor" in message, (
        "the refusal of capacity_factor=0 does not name capacity_factor: %r"
        % (message,))
    message = _refuses(model.ModelError, "a hot expert that is not an expert",
                       lambda: s8.expert_parallel(moe2, world2, batch=2, seq=4,
                                                  hot=4))
    assert "hot" in message, (
        "the refusal of hot=4 on a two-expert model does not name hot: %r"
        % (message,))

    assert s1.plan_bytes(alone) == 0 and s1.step_ticks(world1, alone) == 0, (
        "the one-rank plan moves %r bytes at a cost of %r ticks, not nothing: "
        "a group of one needs no plan at all"
        % (s1.plan_bytes(alone), s1.step_ticks(world1, alone)))
    assert all(not collective.plan.transfers for collective in alone.collectives), (
        "the one-rank plan holds transfers: every collective over one rank is "
        "the empty plan")
    assert s1.plan_bytes(s8.expert_parallel(moe2, world2, batch=2, seq=4)) == s1.plan_bytes(balanced), (
        "two identical expert_parallel calls returned different plans")

    print("check_08: the routing is a table of placements with the row sums "
          "every token and the columns the experts; dropped counts what the "
          "capacity cap refuses and the combine carries only what was kept; "
          "balance_loss is an exact integer that is zero when the experts are "
          "even; and expert_parallel issues the two ragged all-to-alls with the "
          "busiest rank's lengths, priced by the maximum over the ranks and "
          "never by their mean")

# --- stage 9 -----------------------------------------------------------------------
def check_9():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("H1_REPO"), start, os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "distributed-training-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set H1_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call):
        """The message of the refusal `call` must raise, or the mistake named."""
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

    def _split(q, k, v, sizes):
        """The triple list `(q, k, v)` cut into consecutive blocks of `sizes`."""
        blocks = []
        at = 0
        for size in sizes:
            blocks.append((q[at:at + size], k[at:at + size], v[at:at + size]))
            at += size
        return tuple(blocks)

    import fabric
    import model
    import plans

    import stage_01 as s1

    import stage_09 as s

    # ---- online_attention: the same pair for every split -------------------

    q = (2, -1, 3, 0, 4, -2, 1, 5)
    k = (1, 2, -2, 1, 0, 3, -1, 2)
    v = (5, -3, 2, 7, -4, 6, 1, -2)
    want = model.reference_attention(q, k, v)
    assert want == (223899562, 41312837), (
        "the fixture's reference moved: %r, not (223899562, 41312837)" % (want,))

    for split in (1, 2, 4, 8):
        size = len(q) // split
        blocks = _split(q, k, v, (size,) * split)
        got = s.online_attention(blocks)
        assert got == want, (
            "the sequence split into %d blocks accumulated to %r, not the "
            "reference %r: every split must return the identical pair, so the "
            "accumulator must carry the earlier blocks and rescale both parts"
            % (split, got, want))

    unequal = _split(q, k, v, (1, 3, 4))
    got = s.online_attention(unequal)
    assert got == want, (
        "the unequal blocks %r accumulated to %r, not the reference %r"
        % (unequal, got, want))
    assert s.online_attention(_split(q, k, v, (3, 5))) == want, (
        "a two-block unequal split did not land on the reference")

    # a lower pivot in a later block is what the rescale must survive
    assert s.online_attention(_split(q, k, v, (2,) * 4)) == want, (
        "a split whose later block lowers the pivot did not rescale to the "
        "reference: both the numerator and the denominator must shift")

    # ---- online_attention: reduction and sign ------------------------------

    eq_q = (1, 1, 1, 1)
    eq_k = (1, 1, 1, 1)
    eq_v = (1, 2, 3, 4)
    eq_want = model.reference_attention(eq_q, eq_k, eq_v)
    assert eq_want == (5, 2), (
        "the equal-score fixture's reference moved: %r, not (5, 2)" % (eq_want,))
    for split in (1, 2, 4):
        size = 4 // split
        blocks = _split(eq_q, eq_k, eq_v, (size,) * split)
        got = s.online_attention(blocks)
        assert got == eq_want, (
            "the reducible sequence split into %d blocks gave %r, not the "
            "reduced reference %r: the pair is reduced to lowest terms"
            % (split, got, eq_want))

    neg_q = (-2, 3, -1, 4)
    neg_k = (2, -3, 1, -2)
    neg_v = (-5, -3, -2, -7)
    neg_want = model.reference_attention(neg_q, neg_k, neg_v)
    assert s.online_attention(_split(neg_q, neg_k, neg_v, (2, 2))) == neg_want, (
        "the negative-value fixture did not reach %r" % (neg_want,))
    assert s.online_attention(_split(neg_q, neg_k, neg_v, (2, 2)))[0] == neg_want[0], (
        "the numerator's sign is not the reference's")

    # ---- online_attention: the block shape is validated --------------------

    message = _refuses(model.ModelError, "an empty block list",
                       lambda: s.online_attention(()))
    assert "blocks" in message, (
        "the refusal of an empty block list does not name blocks: %r" % (message,))
    message = _refuses(model.ModelError, "a block that is not a triple",
                       lambda: s.online_attention(((1, 2),)))
    assert "blocks" in message, (
        "the refusal of a short block does not name blocks: %r" % (message,))
    message = _refuses(
        model.ModelError, "a block whose q, k and v differ in length",
        lambda: s.online_attention((((1, 2), (3,), (4, 5)),)))
    assert "blocks" in message, (
        "the refusal of unequal q/k/v does not name blocks: %r" % (message,))
    message = _refuses(
        model.ModelError, "a non-int element",
        lambda: s.online_attention((((1, 2), (3, 4), (5, "x")),)))
    assert "blocks" in message, (
        "the refusal of a non-int element does not name blocks: %r" % (message,))
    message = _refuses(
        model.ModelError, "a block side that is empty",
        lambda: s.online_attention((((), (), ()),)))
    assert "blocks" in message, (
        "the refusal of an empty block side does not name blocks: %r" % (message,))
    message = _refuses(
        model.ModelError, "a block with more than three sides",
        lambda: s.online_attention((((1,), (2,), (3,), (4,)),)))
    assert "blocks" in message, (
        "the refusal of a four-sided block does not name blocks: %r" % (message,))

    # ---- context_parallel: the ring of KV blocks ---------------------------

    shape = model.SHAPES["tiny"]
    batch, seq = 2, 8
    for world in (fabric.full(4), fabric.ring(4)):
        for split in (1, 2, 4):
            step = s.context_parallel(shape, world, batch=batch, seq=seq,
                                      split=split)
            members = tuple(world.ranks[:split])
            block = batch * (seq // split) * shape.heads * shape.head_dim() * 2
            # the ledger is the step's own memory, not stage 1's state
            assert step.memory == (s1.MemoryLine("kv", members,
                                                 block * model.ELEMENT_BYTES),), (
                "split=%d on %s has ledger %r, not the kv line of %d bytes per "
                "rank: the KV is the key and the value of the rank's positions"
                % (split, world, step.memory, block * model.ELEMENT_BYTES))
            if split == 1:
                assert step.collectives == (), (
                    "split=1 on %s emits %d collectives: an axis of one is the "
                    "empty plan and costs no comms"
                    % (world, len(step.collectives)))
                assert s1.plan_bytes(step) == 0, (
                    "split=1 on %s moves %r bytes, not nothing"
                    % (world, s1.plan_bytes(step)))
                continue
            assert len(step.collectives) == 1, (
                "split=%d on %s issues %d collectives, not the one ring"
                % (split, world, len(step.collectives)))
            (collective,) = step.collectives
            assert collective.axis == "cp", (
                "the KV collective's axis is %r, not cp" % (collective.axis,))
            assert collective.name == "kv", (
                "the KV collective's name is %r, not kv" % (collective.name,))
            assert collective.algo == "ring", (
                "the KV collective's algo is %r, not ring" % (collective.algo,))
            assert collective.group == members, (
                "split=%d on %s runs over %r, not the first %d ranks"
                % (split, world, collective.group, split))
            assert fabric.legality_problems(world, collective.plan) == (), (
                "the split=%d fixture on %s is not legal: %r"
                % (split, world, fabric.legality_problems(world, collective.plan)))
            steps = plans.steps(collective.plan)
            assert steps == split - 1, (
                "the split=%d ring on %s has %d steps, not one hop per block "
                "minus the block already held, %d" % (split, world, steps, split - 1))
            lengths = {transfer.length for transfer in collective.plan.transfers}
            assert lengths == {block}, (
                "the split=%d ring on %s moves %r elements per hop, not one KV "
                "block of %d: the length counts the heads, the head dimension, "
                "the key and the value, and the batch"
                % (split, world, lengths, block))
            assert s1.plan_bytes(step) == model.ELEMENT_BYTES * (split - 1) * block, (
                "the split=%d ring on %s moves %r bytes per rank, not "
                "4 * %d * %d: every rank forwards one block per hop"
                % (split, world, s1.plan_bytes(step), split - 1, block))
            assert collective.length == (split - 1) * block, (
                "the split=%d collective's length is %r, not the %d elements a "
                "rank moves in all" % (split, collective.length, (split - 1) * block))

    # the ring really is one hop per step on a path topology: the step count of
    # a split=4 ring on four ranks is three
    step4 = s.context_parallel(shape, fabric.ring(4), batch=1, seq=4, split=4)
    assert plans.steps(step4.collectives[0].plan) == 3, (
        "the four-block ring has %r steps, not three"
        % (plans.steps(step4.collectives[0].plan),))

    # two calls are equal (the plan is data)
    again = s.context_parallel(shape, fabric.ring(4), batch=1, seq=4, split=4)
    assert again == step4, "two context_parallel calls do not return equal plans"

    # ---- context_parallel: refusals ----------------------------------------

    message = _refuses(
        model.ModelError, "a split that does not divide the sequence",
        lambda: s.context_parallel(shape, fabric.full(4), batch=1, seq=7, split=2))
    assert "seq" in message or "split" in message, (
        "the refusal of a non-dividing split does not name seq or split: %r"
        % (message,))
    message = _refuses(
        model.ModelError, "a split larger than the world",
        lambda: s.context_parallel(shape, fabric.full(4), batch=1, seq=8, split=8))
    assert "split" in message, (
        "the refusal of a split larger than the world does not name split: %r"
        % (message,))
    message = _refuses(
        model.ModelError, "a split below one",
        lambda: s.context_parallel(shape, fabric.full(4), batch=1, seq=8, split=0))
    assert "split" in message, (
        "the refusal of split=0 does not name split: %r" % (message,))
    message = _refuses(
        model.ModelError, "a non-positive batch",
        lambda: s.context_parallel(shape, fabric.full(4), batch=0, seq=8, split=2))
    assert "batch" in message, (
        "the refusal of batch=0 does not name batch: %r" % (message,))
    message = _refuses(
        model.ModelError, "a non-positive seq",
        lambda: s.context_parallel(shape, fabric.full(4), batch=1, seq=0, split=1))
    assert "seq" in message, (
        "the refusal of seq=0 does not name seq: %r" % (message,))
    message = _refuses(
        model.ModelError, "a shape that is not a ModelShape",
        lambda: s.context_parallel("tiny", fabric.full(4), batch=1, seq=8, split=2))
    assert "shape" in message, (
        "the refusal of a non-shape does not name shape: %r" % (message,))

    print("check_09: sequence / context parallel — online_attention accumulates "
          "the KV blocks to the reference pair for every split, rescaling both "
          "parts of the running accumulator, and context_parallel rotates the KV "
          "blocks around the ring in split-1 hops priced per block")

# --- stage 10 ----------------------------------------------------------------------
def check_10():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    ROOMY = 1 << 62

    def _repo(start=None):
        for candidate_start in (os.environ.get("H1_REPO"), start, os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "distributed-training-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set H1_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call):
        """The message of the refusal `call` must raise, or the mistake named."""
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

    def _factorizations(gpus):
        """Every `(dp, tp, pp, ep, cp)` of positive ints multiplying to `gpus`, in
        the order the check ticks them: the whole candidate space, written out here
        so a stage that quietly drops an axis from its own search is caught."""
        out = []
        for dp in range(1, gpus + 1):
            if gpus % dp:
                continue
            for tp in range(1, gpus // dp + 1):
                if (gpus // dp) % tp:
                    continue
                for pp in range(1, gpus // (dp * tp) + 1):
                    if (gpus // (dp * tp)) % pp:
                        continue
                    rest = gpus // (dp * tp * pp)
                    for ep in range(1, rest + 1):
                        if rest % ep:
                            continue
                        out.append((dp, tp, pp, ep, rest // ep))
        return tuple(sorted(out))

    import fabric
    import model
    import plans

    import stage_01 as s1
    import stage_02 as s2
    import stage_03 as s3
    import stage_04 as s4
    import stage_06 as s6
    import stage_08 as s8
    import stage_09 as s9
    import stage_10 as s

    names = ("dp", "tp", "pp", "ep", "cp")

    def axes_of(axes, axis):
        """The size the `axes` tuple gives one axis, by name."""
        return axes[names.index(axis)]

    def no_axis_of_one(axes, plan, where):
        """Every collective belongs to an axis whose size is larger than one."""
        for collective in plan.collectives:
            assert axes_of(axes, collective.axis) > 1, (
                "%s: %r has %d-rank %s axis but still emits a %r collective "
                "of %d elements: an axis of one is the empty plan and costs no "
                "comms" % (where, axes, axes_of(axes, collective.axis),
                           collective.axis, collective.name, collective.length))

    def legal(world, plan, where):
        """Every collective's plan is legal on the world it is priced on."""
        for collective in plan.collectives:
            problems = fabric.legality_problems(world, collective.plan)
            assert problems == (), (
                "%s: the %s/%s collective is not legal on %s: %r"
                % (where, collective.axis, collective.name, world, problems))

    def priced(world, gpus, shape, **kw):
        """`{axes: ticks}` for every candidate the configuration can build and
        fit — the argmin the choice is checked against, ticked here."""
        got = {}
        for candidate in _factorizations(gpus):
            try:
                chosen, plan = s.configure(shape, world, gpus=gpus, axes=candidate,
                                           **kw)
            except model.ModelError:
                continue
            except fabric.FabricError:
                continue
            assert chosen == candidate, (
                "configure(axes=%r) answered %r: a configuration asked for is "
                "the configuration built" % (candidate, chosen))
            got[candidate] = s1.step_ticks(world, plan)
        return got

    tiny = model.SHAPES["tiny"]
    one_b = model.SHAPES["1b"]
    full1 = fabric.full(1)
    full2 = fabric.full(2)
    full4 = fabric.full(4)
    full8 = fabric.full(8)
    ring8 = fabric.ring(8)
    switch8 = fabric.switch(8, width=4)
    moe2 = model.ModelShape(2, 4, 2, 8, 12, experts=2, top_k=2)
    moe8 = model.ModelShape(2, 8, 4, 16, 32, experts=8, top_k=2)
    budget = s.DEFAULT_MEMORY_BUDGET
    assert budget == 8 << 30, (
        "the default memory budget moved: %r, not eight gibibytes" % (budget,))
    assert s.AXIS_ORDER == names, (
        "the axis order moved: %r, not %r" % (s.AXIS_ORDER, names))

    params = tiny.params()
    assert params == 388, "the tiny fixture moved: %d parameters, not 388" % (params,)
    assert one_b.params() == 1093224448, (
        "the 1b fixture moved: %d parameters" % (one_b.params(),))

    # ---- one device is the single-device reference -------------------------

    for shape, world, kw in ((tiny, full1, {}), (one_b, full1, {"memory_budget": ROOMY})):
        axes, plan = s.configure(shape, world, gpus=1, **kw)
        assert axes == (1, 1, 1, 1, 1), (
            "gpus=1 chose %r, not the single-device split (1, 1, 1, 1, 1)" % (axes,))
        assert plan.collectives == (), (
            "gpus=1 on %s emits %d collectives: one device moves nothing and "
            "costs no comms" % (world, len(plan.collectives)))
        assert plan.compute > 0, (
            "gpus=1 on %s owns no compute: the single-device reference is the "
            "step's arithmetic" % (world,))
        report = s.report(shape, world, plan)
        assert report["step_ticks"] == plan.compute, (
            "gpus=1 on %s ticks %r, not its compute %r: with no collectives the "
            "step is its compute" % (world, report["step_ticks"], plan.compute))
        assert report["comms"] == 0 and report["bytes_per_rank"] == 0, (
            "gpus=1 on %s moves %r bytes and ticks %r of comms, not nothing"
            % (world, report["bytes_per_rank"], report["comms"]))
        want = (model.PARAM_BYTES + model.PARAM_BYTES + model.MASTER_BYTES
                + model.OPTIMIZER_BYTES) * shape.params()
        assert sum(report["memory_by_rank"].values()) == want + shape.activation_bytes(1, 1), (
            "gpus=1 on %s holds %r bytes per rank, not the whole 16 B/parameter "
            "state plus the activations, %r"
            % (world, sum(report["memory_by_rank"].values()),
               want + shape.activation_bytes(1, 1)))
        assert report == s.report(shape, world, plan), (
            "two reports of one plan are not equal")

    # ---- the axes multiply to the devices, and every candidate builds ------

    for shape, world, gpus in ((tiny, full1, 1), (tiny, full2, 2), (tiny, full4, 4),
                               (one_b, full8, 8), (one_b, switch8, 8)):
        for candidate in _factorizations(gpus):
            product = 1
            for size in candidate:
                product *= size
            assert product == gpus, (
                "%r does not multiply to %d" % (candidate, gpus))
        axes, plan = s.configure(shape, world, gpus=gpus)
        product = 1
        for size in axes:
            product *= size
        assert product == gpus and len(axes) == 5, (
            "the configuration chosen for %d devices is %r: the five axes "
            "multiply to the devices they partition" % (gpus, axes))
        assert max(axes) * gpus > 0 and min(axes) >= 1, (
            "the configuration %r holds a non-positive axis" % (axes,))
        assert s.configure(shape, world, gpus=gpus) == (axes, plan), (
            "two configure calls for %r on %s do not return equal configurations"
            % (gpus, world))

    # ---- an axis of one emits nothing --------------------------------------

    for candidate in ((2, 2, 1, 1, 1), (2, 1, 2, 1, 1), (1, 2, 2, 1, 1),
                      (4, 1, 1, 1, 1), (1, 4, 1, 1, 1), (1, 1, 4, 1, 1)):
        axes, plan = s.configure(tiny, full4, gpus=4, axes=candidate,
                                 memory_budget=ROOMY)
        assert axes == candidate, (
            "configure(axes=%r) answered %r" % (candidate, axes))
        no_axis_of_one(axes, plan, "axes=%r on %s" % (candidate, full4))
        legal(full4, plan, "axes=%r on %s" % (candidate, full4))
    for candidate in ((1, 1, 1, 1, 4), (1, 2, 1, 1, 2), (1, 1, 2, 1, 2),
                      (1, 1, 1, 2, 2)):
        shape = moe2 if axes_of(candidate, "ep") > 1 else tiny
        axes, plan = s.configure(shape, full4, gpus=4, axes=candidate,
                                 batch=2, seq=8, memory_budget=ROOMY)
        no_axis_of_one(axes, plan, "axes=%r on %s" % (candidate, full4))
    # the whole model on one rank again: nothing at all
    axes, plan = s.configure(tiny, full1, gpus=1, batch=2, seq=8)
    check_all = [collective for collective in plan.collectives]
    assert check_all == [], "the single-device split emitted %r" % (check_all,)

    # ---- every axis's own collectives, over its own ranks ------------------

    axes, plan = s.configure(one_b, full8, gpus=8, axes=(1, 4, 2, 1, 1),
                             memory_budget=ROOMY)
    block = 1 * 1 * one_b.hidden
    tp = [c for c in plan.collectives if c.axis == "tp"]
    assert len(tp) == 2, (
        "tensor parallel emitted %d collectives, not the forward's and the "
        "backward's two" % (len(tp),))
    for collective in tp:
        assert collective.group == tuple(full8.ranks[:4]), (
            "the tp collective runs over %r, not the first four ranks"
            % (collective.group,))
        assert collective.length == block, (
            "the tp collective moves %d elements, not the block's %d"
            % (collective.length, block))
    assert len({c.name for c in tp}) == 2, (
        "the two tp collectives share the name %r: one is the forward's, one "
        "the backward's" % ({c.name for c in tp},))

    axes, plan = s.configure(tiny, full4, gpus=4, axes=(1, 1, 4, 1, 1),
                             batch=2, seq=4, memory_budget=ROOMY)
    pp = [c for c in plan.collectives if c.axis == "pp"]
    assert len(pp) == 2 * 2 * (4 - 1), (
        "the pipeline emitted %d sends, not one activation and one gradient per "
        "micro-batch per boundary, %d" % (len(pp), 2 * 2 * 3))
    assert {tuple(c.group) for c in pp} == {("r0", "r1"), ("r1", "r2"), ("r2", "r3")}, (
        "the pipeline's sends run over %r, not the stage boundaries"
        % ({tuple(c.group) for c in pp},))
    assert all(c.length == 4 * tiny.hidden for c in pp), (
        "a pipeline send moves %r elements, not one micro-batch's seq * hidden, "
        "%d" % ([c.length for c in pp], 4 * tiny.hidden))
    assert all(c.algo == "p2p" for c in pp), (
        "a pipeline send's algorithm is %r, not p2p" % ({c.algo for c in pp},))
    assert {c.name for c in pp} == {"activations", "grads"}, (
        "the pipeline's sends are named %r, not the activation going forward and "
        "the gradient coming back" % ({c.name for c in pp},))
    # the step's compute is stage 2's number, on every rank of every split
    base = s.configure(tiny, full1, gpus=1, batch=2, seq=4)[1].compute
    course = s2.data_parallel(tiny, full1, batch=2, seq=4).compute
    assert base == course, (
        "the single-device step computes %r, not the course's own compute model, "
        "%r" % (base, course))
    assert plan.compute == course, (
        "a four-stage pipeline computes %r per rank, not the step's own %r: the "
        "axes' collectives run beside the arithmetic, not instead of it"
        % (plan.compute, course))
    axes, bp_plan = s.configure(one_b, full8, gpus=8, axes=(1, 8, 1, 1, 1),
                                seq=512, memory_budget=ROOMY)
    course_bp = s2.data_parallel(one_b, full1, batch=1, seq=512).compute
    assert bp_plan.compute == course_bp != base, (
        "a step of 512 positions computes %r, not the step's own arithmetic %r: "
        "the compute follows the batch and the sequence, not the configuration"
        % (bp_plan.compute, course_bp))
    axes, tp_plan = s.configure(tiny, full4, gpus=4, axes=(1, 4, 1, 1, 1),
                                batch=2, seq=4, memory_budget=ROOMY)
    assert tp_plan.compute == course, (
        "four-way tensor parallel computes %r, not the step's own %r: sharding "
        "the block splits the state and the traffic, not the step"
        % (tp_plan.compute, course))
    # the sends are the ones stage 6's schedule exchanges
    forwards = sum(1 for slot in s6.one_f_one_b(4, 2) if slot.phase == "f")
    assert forwards == 4 * 2 and len(pp) == 2 * (forwards // 4) * (4 - 1), (
        "the pipeline's %d sends are not the %d micro-batches' activations and "
        "gradients per boundary that stage 6's schedule exchanges"
        % (len(pp), forwards // 4))

    axes, plan = s.configure(tiny, full4, gpus=4, axes=(1, 1, 1, 1, 4),
                             batch=2, seq=8, memory_budget=ROOMY)
    cp = [c for c in plan.collectives if c.axis == "cp"]
    block = 2 * (8 // 4) * tiny.heads * tiny.head_dim() * 2
    assert len(cp) == 1 and cp[0].name == "kv" and cp[0].algo == "ring", (
        "the context axis emitted %r, not one KV ring collective"
        % ([(c.name, c.algo) for c in cp],))
    assert cp[0].group == tuple(full4.ranks), (
        "the KV ring runs over %r, not the ranks that own blocks, %r"
        % (cp[0].group, tuple(full4.ranks)))
    assert cp[0].length == (4 - 1) * block, (
        "the KV ring moves %d elements per rank, not one block per hop, %d"
        % (cp[0].length, (4 - 1) * block))
    ref = s9.context_parallel(tiny, full4, batch=2, seq=8, split=4)
    assert s1.plan_bytes(plan) == s1.plan_bytes(ref), (
        "the composed context axis moves %r bytes, not stage 9's own %r"
        % (s1.plan_bytes(plan), s1.plan_bytes(ref)))
    assert tuple(line for line in plan.memory if line.what == "kv") == ref.memory, (
        "the composed KV ledger is %r, not stage 9's own %r"
        % (tuple(line for line in plan.memory if line.what == "kv"), ref.memory))

    # a strided context group: the layout's own ranks, not the first ones
    axes, plan = s.configure(tiny, full8, gpus=8, axes=(1, 2, 1, 1, 4),
                             batch=2, seq=8, memory_budget=ROOMY)
    cp = [c for c in plan.collectives if c.axis == "cp"]
    assert cp and cp[0].group == ("r0", "r2", "r4", "r6"), (
        "with tp=2 the context group is %r, not the ranks that differ only in "
        "cp, ('r0', 'r2', 'r4', 'r6')" % (cp[0].group if cp else None,))
    kv = [line for line in plan.memory if line.what == "kv"]
    assert kv and kv[0].group == ("r0", "r2", "r4", "r6"), (
        "the KV ledger lives over %r, not the ranks that rotate it, "
        "('r0', 'r2', 'r4', 'r6')" % ([line.group for line in kv],))

    axes, plan = s.configure(moe8, full8, gpus=8, axes=(1, 1, 1, 8, 1),
                             batch=4, seq=8, memory_budget=ROOMY)
    ep = [c for c in plan.collectives if c.axis == "ep"]
    assert len(ep) == 2 and {c.name for c in ep} == {"dispatch", "combine"}, (
        "the expert axis emitted %r, not the dispatch and the combine"
        % ([(c.name, c.algo) for c in ep],))
    ref = s8.expert_parallel(moe8, full8, batch=4, seq=8)
    assert s1.plan_bytes(plan) == s1.plan_bytes(ref), (
        "the composed expert axis moves %r bytes, not stage 8's own %r"
        % (s1.plan_bytes(plan), s1.plan_bytes(ref)))
    # an expert axis that is not the whole world: its own ranks, not the world
    full16 = fabric.full(16)
    sub8 = plans.group_fabric(full16, tuple(full16.ranks)[:8])
    axes, plan = s.configure(moe8, full16, gpus=16, axes=(2, 1, 1, 8, 1),
                             batch=4, seq=8, memory_budget=ROOMY)
    ep = [c for c in plan.collectives if c.axis == "ep"]
    ref = s8.expert_parallel(moe8, sub8, batch=4, seq=8)
    assert ep and [c.length for c in ep] == [c.length for c in ref.collectives], (
        "on sixteen devices with dp=2 the expert axis moves %r, not stage 8's "
        "own %r over the eight ranks that own the experts"
        % ([c.length for c in ep], [c.length for c in ref.collectives]))

    # ---- the dp axis: stage 2, the ZeRO ladder, and the local shard --------

    grads = one_b.params()
    b2 = 25_000_000
    axes, plan = s.configure(one_b, full8, gpus=8, axes=(8, 1, 1, 1, 1),
                             bucket_bytes=b2, memory_budget=ROOMY)
    ref = s2.data_parallel(one_b, full8, batch=1, seq=1, bucket_bytes=b2)
    assert len(plan.collectives) == len(ref.collectives), (
        "the dp axis made %d buckets where stage 2 makes %d"
        % (len(plan.collectives), len(ref.collectives)))
    assert [c.length for c in plan.collectives] == [c.length for c in ref.collectives], (
        "the dp axis's buckets move different bytes than stage 2's")
    assert [(c.axis, c.name, c.algo) for c in plan.collectives] == \
           [(c.axis, c.name, c.algo) for c in ref.collectives], (
        "the dp axis's buckets are %r, not stage 2's own %r: the composed axis "
        "is stage 2's plan, bucket for bucket"
        % ([(c.axis, c.name, c.algo) for c in plan.collectives],
           [(c.axis, c.name, c.algo) for c in ref.collectives]))
    want = 2 * grads * (8 - 1) // 8 * model.ELEMENT_BYTES
    assert s1.plan_bytes(plan) == s1.plan_bytes(ref) == want, (
        "the pure data-parallel step moves %r bytes per rank, not stage 2's "
        "own 2*grads*(N-1)/N, %r" % (s1.plan_bytes(plan), want))
    assert s1.step_ticks(full8, plan) == s1.step_ticks(full8, ref), (
        "the dp axis ticks %r, not stage 2's own %r"
        % (s1.step_ticks(full8, plan), s1.step_ticks(full8, ref)))
    small = s.configure(one_b, full8, gpus=8, axes=(8, 1, 1, 1, 1),
                        bucket_bytes=4_000_000, memory_budget=ROOMY)[1]
    assert len(small.collectives) > len(plan.collectives), (
        "a smaller bucket did not make more buckets: the bucket is the threshold "
        "stage 2 cuts the gradient at")
    # a bucket the group does not divide: stage 2 pads it to the ring's chunks
    axes, plan = s.configure(tiny, full4, gpus=4, axes=(4, 1, 1, 1, 1),
                             bucket_bytes=1_000, memory_budget=ROOMY)
    ref = s2.data_parallel(tiny, full4, batch=1, seq=1, bucket_bytes=1_000)
    assert [c.length for c in plan.collectives] == [c.length for c in ref.collectives], (
        "with a bucket the group does not divide, the dp axis moves %r where "
        "stage 2 moves %r: the ring's chunks are equal, so the buffer is padded "
        "to the group's rank count" % ([c.length for c in plan.collectives],
                                       [c.length for c in ref.collectives]))
    for stage, count in ((1, 1), (2, 2)):
        axes, plan = s.configure(one_b, full8, gpus=8, axes=(8, 1, 1, 1, 1),
                                 zero=stage, memory_budget=ROOMY)
        ref = s3.zero(one_b, full8, stage=stage)
        assert len(plan.collectives) == len(ref.collectives) == count, (
            "ZeRO-%d emits %d collectives, not stage 3's own %d"
            % (stage, len(plan.collectives), len(ref.collectives)))
        assert s1.plan_bytes(plan) == s1.plan_bytes(ref), (
            "ZeRO-%d moves %r bytes, not stage 3's own %r"
            % (stage, s1.plan_bytes(plan), s1.plan_bytes(ref)))
        assert [(c.axis, c.name, c.algo) for c in plan.collectives] == \
               [(c.axis, c.name, c.algo) for c in ref.collectives], (
            "ZeRO-%d's collectives are %r, not stage 3's own %r"
            % (stage, [(c.axis, c.name, c.algo) for c in plan.collectives],
               [(c.axis, c.name, c.algo) for c in ref.collectives]))
    layer_bytes = model.PARAM_BYTES * sum(
        t.elements for t in one_b.tensors() if t.name.startswith("layer.0."))
    axes, plan = s.configure(one_b, full8, gpus=8, axes=(8, 1, 1, 1, 1),
                             zero=3, wrap_bytes=layer_bytes, memory_budget=ROOMY)
    ref = s4.fully_sharded(one_b, full8, wrap_bytes=layer_bytes)
    assert len(plan.collectives) == len(ref.collectives), (
        "FSDP emits %d collectives, not stage 4's own %d per wrap unit"
        % (len(plan.collectives), len(ref.collectives)))
    assert s1.plan_bytes(plan) == s1.plan_bytes(ref), (
        "FSDP moves %r bytes, not stage 4's own %r"
        % (s1.plan_bytes(plan), s1.plan_bytes(ref)))
    assert [(c.axis, c.name, c.algo) for c in plan.collectives] == \
           [(c.axis, c.name, c.algo) for c in ref.collectives], (
        "FSDP's per-unit collectives are %r, not stage 4's own %r"
        % ([(c.axis, c.name, c.algo) for c in plan.collectives],
           [(c.axis, c.name, c.algo) for c in ref.collectives]))
    # the same rung with the default wrap unit, and a composed local shard
    axes, plan = s.configure(one_b, full8, gpus=8, axes=(8, 1, 1, 1, 1),
                             zero=3, memory_budget=ROOMY)
    ref = s4.fully_sharded(one_b, full8, wrap_bytes=layer_bytes)
    assert s1.plan_bytes(plan) == s1.plan_bytes(ref), (
        "a wrap of no given size moves %r bytes, not the one transformer layer "
        "stage 4 wraps at that size, %r: the default unit is a layer, not the "
        "model" % (s1.plan_bytes(plan), s1.plan_bytes(ref)))
    tensors = one_b.tensors()
    units = s4.wrap_policy(one_b, plans.group_fabric(full8, ("r0", "r4")),
                           wrap_bytes=layer_bytes)
    want = 0
    for unit in units:
        elements = sum(tensors[index].elements for index in unit)
        words = model.ceil_div(model.ceil_div(elements, 4) * model.PARAM_BYTES,
                               fabric.ELEMENT_BYTES)
        padded = model.ceil_div(words, 2) * 2
        want += 2 * (padded * (2 - 1) // 2)
    axes, plan = s.configure(one_b, full8, gpus=8, axes=(2, 4, 1, 1, 1),
                             zero=3, wrap_bytes=layer_bytes, memory_budget=ROOMY)
    dp_words = sum(c.length for c in plan.collectives if c.axis == "dp")
    assert dp_words == want, (
        "with dp=2 and the weights split four ways FSDP moves %d elements, not "
        "the %d a wrap unit of a quarter of the parameters costs: the rung is "
        "sized on the shard the rank owns" % (dp_words, want))

    # the ledger is 16 B/parameter, sharded exactly as the ladder says
    replicated = {"params": 2 * grads, "gradients": 2 * grads, "masters": 4 * grads,
                  "optimizer": 8 * grads}
    ladder = {
        0: dict(replicated),
        1: {"params": 2 * grads, "gradients": 2 * grads,
            "masters": model.ceil_div(4 * grads, 8),
            "optimizer": model.ceil_div(8 * grads, 8)},
        2: {"params": 2 * grads, "gradients": model.ceil_div(2 * grads, 8),
            "masters": model.ceil_div(4 * grads, 8),
            "optimizer": model.ceil_div(8 * grads, 8)},
        3: {"params": model.ceil_div(2 * grads, 8),
            "gradients": model.ceil_div(2 * grads, 8),
            "masters": model.ceil_div(4 * grads, 8),
            "optimizer": model.ceil_div(8 * grads, 8)},
    }
    for stage, want in ladder.items():
        axes, plan = s.configure(one_b, full8, gpus=8, axes=(8, 1, 1, 1, 1),
                                 zero=stage, memory_budget=ROOMY)
        got = s.report(one_b, full8, plan)["memory_by_rank"]
        for what, size in want.items():
            assert got.get(what) == size, (
                "ZeRO-%d's %s ledger is %r, not the %d bytes per rank the "
                "ladder shards it to" % (stage, what, got.get(what), size))
        assert got.get("activations") == one_b.activation_bytes(1, 1), (
            "ZeRO-%d reports %r activation bytes, not the step's own %d"
            % (stage, got.get("activations"), one_b.activation_bytes(1, 1)))
        assert "kv" not in got, (
            "ZeRO-%d on one rank per axis reports a kv line, %r: nothing rotates "
            "when there is no context axis" % (stage, sorted(got)))

    # the activations are the only line the layers and the sequence shard
    axes, plan = s.configure(tiny, full8, gpus=8, axes=(1, 1, 4, 1, 2),
                             batch=2, seq=8, memory_budget=ROOMY)
    got = s.report(tiny, full8, plan)["memory_by_rank"]
    assert got["activations"] == model.ceil_div(tiny.activation_bytes(2, 8), 4 * 2), (
        "with pp=4 and cp=2 the rank holds %r activation bytes, not the step's "
        "%d over the 8 ranks that shard it"
        % (got["activations"], tiny.activation_bytes(2, 8)))
    assert got["params"] == model.ceil_div(model.PARAM_BYTES * tiny.params(), 4), (
        "with tp=1, pp=4 and dp=1 the rank holds %r parameter bytes, not the "
        "model's %d over the four stages that hold it: only the axes that split "
        "the weights, and the sequence, cut the state"
        % (got["params"], model.PARAM_BYTES * tiny.params()))
    assert got["kv"] == (model.ELEMENT_BYTES * 2 * (8 // 2) * tiny.heads
                         * tiny.head_dim() * 2), (
        "the kv line is %r bytes, not the rank's block of the sequence"
        % (got["kv"],))

    # the dp axis is sized on the local shard, not the whole model
    local = model.ceil_div(one_b.params(), 4)
    axes, plan = s.configure(one_b, full8, gpus=8, axes=(2, 4, 1, 1, 1),
                             bucket_bytes=25_000_000, memory_budget=ROOMY)
    dp = [c for c in plan.collectives if c.axis == "dp"]
    assert dp and all(c.group == ("r0", "r4") for c in dp), (
        "with dp=2 the gradient all-reduce runs over %r, not the strided pair "
        "the layout gives the axis" % ([tuple(c.group) for c in dp],))
    dp_bytes = sum(model.ELEMENT_BYTES * c.length for c in dp)
    assert dp_bytes == model.ELEMENT_BYTES * local * (2 - 1), (
        "the composed dp axis moves %r bytes per rank, not the local gradient's "
        "2 * (P/4) * (N-1)/N, %r"
        % (dp_bytes, model.ELEMENT_BYTES * local * (2 - 1)))
    assert dp[0].length < 2 * one_b.params(), (
        "the dp collective still moves the whole model's gradient, %d elements"
        % (dp[0].length,))

    # ---- the choice is the argmin of step_ticks over the candidates --------

    for label, shape, world, gpus, kw in (
            ("1b on full(8)", one_b, full8, 8, {}),
            ("1b on switch(8, width=4)", one_b, switch8, 8, {}),
            ("tiny on full(4)", tiny, full4, 4, {}),
            ("moe on full(8)", moe8, full8, 8, {"batch": 4, "seq": 8})):
        ticks = priced(world, gpus, shape, **kw)
        assert len(ticks) >= 3, (
            "%s: only %d configurations could be priced, so there is no choice "
            "to make" % (label, len(ticks)))
        assert len(set(ticks.values())) > 1, (
            "%s: every configuration ticks the same, so the fixture cannot tell "
            "an argmin from a fashion" % (label,))
        chosen, plan = s.configure(shape, world, gpus=gpus, **kw)
        assert chosen in ticks, (
            "%s: the chosen %r is not one of the configurations that build and "
            "fit" % (label, chosen))
        best = min(ticks.values())
        assert ticks[chosen] == best, (
            "%s: the chosen %r ticks %d, but %r ticks the least of the "
            "candidates at %d: the split is chosen by its bytes, not by fashion"
            % (label, chosen, ticks[chosen],
               min(ticks, key=lambda c: ticks[c]), best))
        got = s.report(shape, world, plan)
        assert sum(got["memory_by_rank"].values()) <= (kw.get("memory_budget", budget)), (
            "%s: the chosen %r holds %d bytes per rank, more than the budget"
            % (label, chosen, sum(got["memory_by_rank"].values())))
        no_axis_of_one(chosen, plan, label)
        legal(world, plan, label)
        assert s.configure(shape, world, gpus=gpus, axes=chosen, **kw)[1] == plan, (
            "%s: the plan the free choice returned for %r is not the plan those "
            "axes build when asked for, so the returned plan belongs to another "
            "split" % (label, chosen))

    # the topology decides, not the axis that is fashionable
    ticks = priced(switch8, 8, one_b)
    chosen = s.configure(one_b, switch8, gpus=8)[0]
    assert ticks[chosen] < ticks[(1, 8, 1, 1, 1)], (
        "on the two-level fabric the chosen %r ticks %d, but the whole-world "
        "tensor-parallel split ticks %d: a split of the same axes is not the "
        "same price on a different fabric, and fashion cannot price it"
        % (chosen, ticks[chosen], ticks[(1, 8, 1, 1, 1)]))
    ticks = priced(full8, 8, moe8, batch=4, seq=8)
    chosen = s.configure(moe8, full8, gpus=8, batch=4, seq=8)[0]
    assert ticks[chosen] < ticks[(1, 8, 1, 1, 1)], (
        "with eight experts over eight devices the chosen %r ticks %d, but the "
        "tensor-parallel split ticks %d"
        % (chosen, ticks[chosen], ticks[(1, 8, 1, 1, 1)]))

    # ---- the report derives every number from the plan ---------------------

    for label, shape, world, axes, kw in (
            ("1b tp=8", one_b, full8, (1, 8, 1, 1, 1), {"memory_budget": ROOMY}),
            ("1b switch dp=8", one_b, switch8, (8, 1, 1, 1, 1),
             {"bucket_bytes": 4_000_000, "memory_budget": ROOMY}),
            ("moe cp=4 tp=2", moe8, full8, (1, 2, 1, 1, 4),
             {"batch": 2, "seq": 4, "memory_budget": ROOMY}),
            ("tiny all one but pp", tiny, full4, (1, 1, 4, 1, 1),
             {"batch": 2, "seq": 2, "memory_budget": ROOMY})):
        axes, plan = s.configure(shape, world, gpus=len(world.ranks), axes=axes, **kw)
        report = s.report(shape, world, plan)
        assert set(report) == {"step_ticks", "compute", "comms", "bytes_per_rank",
                               "memory_by_rank"}, (
            "%s: the report's keys are %r, not exactly the five the contract "
            "freezes" % (label, sorted(report)))
        assert report["step_ticks"] == s1.step_ticks(world, plan), (
            "%s: the report ticks %r, but stage 1 prices the plan at %r: the "
            "report recomputes, it never declares"
            % (label, report["step_ticks"], s1.step_ticks(world, plan)))
        assert report["bytes_per_rank"] == s1.plan_bytes(plan), (
            "%s: the report moves %r bytes per rank, but the plan's own "
            "collectives move %r" % (label, report["bytes_per_rank"],
                                     s1.plan_bytes(plan)))
        assert report["compute"] == plan.compute, (
            "%s: the report's compute is %r, not the plan's %r"
            % (label, report["compute"], plan.compute))
        course_compute = s2.data_parallel(
            shape, full1, batch=kw.get("batch", 1), seq=kw.get("seq", 1)).compute
        assert report["compute"] == course_compute, (
            "%s: the report computes %r, not the course's own compute model's "
            "%r: the step's arithmetic is stage 2's number, not something the "
            "configuration declares" % (label, report["compute"], course_compute))
        comms = 0
        for collective in plan.collectives:
            comms += s1.plan_ticks(world, collective.plan)
        assert report["comms"] == comms, (
            "%s: the report's comms are %r, not the plan's collectives' own %r"
            % (label, report["comms"], comms))
        folded = {}
        for line in plan.memory:
            folded[line.what] = folded.get(line.what, 0) + line.bytes
        assert report["memory_by_rank"] == folded, (
            "%s: the report's memory ledger is %r, not the plan's own %r"
            % (label, report["memory_by_rank"], folded))
        assert report["step_ticks"] == max(report["compute"], report["comms"]), (
            "%s: the step ticks %r, not the larger of its compute %r and its "
            "comms %r: comms run beside compute and are never added to it"
            % (label, report["step_ticks"], report["compute"], report["comms"]))
        assert report == s.report(shape, world, plan), (
            "%s: two reports of one plan are not equal" % (label,))

    axes, plan = s.configure(one_b, full8, gpus=8, axes=(1, 8, 1, 1, 1),
                             memory_budget=ROOMY)
    report = s.report(one_b, full8, plan)
    assert report["comms"] > 0 and report["compute"] > 0, (
        "the fixture has no comms or no compute, so the overlap rule is not "
        "tested: %r" % (report,))
    assert report["step_ticks"] != report["compute"] + report["comms"], (
        "the step ticks %r, the sum of its compute and comms: comms are hidden "
        "behind compute, never added to them" % (report["step_ticks"],))
    assert report["step_ticks"] == max(report["compute"], report["comms"])

    # ---- the refusals ------------------------------------------------------

    message = _refuses(
        model.ModelError, "axes that do not multiply to the devices",
        lambda: s.configure(tiny, full4, gpus=4, axes=(2, 3, 1, 1, 1)))
    assert "6" in message and "4" in message, (
        "the refusal of a split that multiplies to 6 rather than 4 does not "
        "name both numbers: %r" % (message,))
    message = _refuses(
        model.ModelError, "a gpus that is not the world's rank count",
        lambda: s.configure(tiny, full4, gpus=8))
    assert "8" in message and "4" in message, (
        "the refusal of gpus=8 on a four-rank world does not name both numbers: "
        "%r" % (message,))
    message = _refuses(
        model.ModelError, "a gpus below one",
        lambda: s.configure(tiny, full4, gpus=0))
    assert "gpus" in message, (
        "the refusal of gpus=0 does not name gpus: %r" % (message,))
    message = _refuses(
        model.ModelError, "a negative memory budget",
        lambda: s.configure(tiny, full4, gpus=4, memory_budget=-1))
    assert "memory_budget" in message and "negative" in message, (
        "the refusal of a negative budget does not name memory_budget as a "
        "negative count: %r" % (message,))
    message = _refuses(
        model.ModelError, "a ZeRO rung that is not on the ladder",
        lambda: s.configure(tiny, full4, gpus=4, zero=9))
    assert "zero" in message, (
        "the refusal of zero=9 does not name zero: %r" % (message,))
    message = _refuses(
        model.ModelError, "a non-positive batch",
        lambda: s.configure(tiny, full4, gpus=4, batch=0))
    assert "batch" in message, (
        "the refusal of batch=0 does not name batch: %r" % (message,))
    message = _refuses(
        model.ModelError, "a non-positive seq",
        lambda: s.configure(tiny, full4, gpus=4, seq=0))
    assert "seq" in message, (
        "the refusal of seq=0 does not name seq: %r" % (message,))
    message = _refuses(
        model.ModelError, "an axis below one",
        lambda: s.configure(tiny, full4, gpus=4, axes=(0, 4, 1, 1, 1)))
    assert "dp" in message, (
        "the refusal of dp=0 does not name the dp axis: %r" % (message,))
    message = _refuses(
        model.ModelError, "an axes tuple that is not five long",
        lambda: s.configure(tiny, full4, gpus=4, axes=(1, 4, 1, 1)))
    assert "axes" in message, (
        "the refusal of a four-axis tuple does not name axes: %r" % (message,))

    # a configuration that cannot fit names the axis and both numbers
    held = (model.PARAM_BYTES + model.PARAM_BYTES + model.MASTER_BYTES
            + model.OPTIMIZER_BYTES) * one_b.params() + one_b.activation_bytes(1, 1)
    message = _refuses(
        model.ModelError, "eight-way data parallel of a 1B model",
        lambda: s.configure(one_b, full8, gpus=8, axes=(8, 1, 1, 1, 1)))
    assert "dp" in message, (
        "the refusal does not name the axis that shards least of the state: %r"
        % (message,))
    assert str(held) in message, (
        "the refusal does not name the %d bytes the configuration wants: %r"
        % (held, message))
    assert str(budget) in message, (
        "the refusal does not name the %d-byte budget: %r" % (budget, message))
    message = _refuses(
        model.ModelError, "a world where no split fits",
        lambda: s.configure(one_b, full8, gpus=8, memory_budget=1024))
    assert "memory_budget" in message and "1024" in message, (
        "the refusal of a world where nothing fits does not name the budget and "
        "its number: %r" % (message,))
    message = _refuses(
        model.ModelError, "a split whose state is sharded by nothing but the "
        "sequence axis",
        lambda: s.configure(one_b, full8, gpus=8, axes=(1, 1, 2, 1, 4), seq=4))
    assert "cp" in message, (
        "the refusal of a split that holds 16 B/parameter over two ranks names "
        "%r, not the cp axis, which shards least of the optimizer line: the "
        "offender is the axis to grow" % (message,))
    message = _refuses(
        model.ModelError, "an optimizer state that does not fit any shard count",
        lambda: s.configure(one_b, full8, gpus=8, axes=(8, 1, 1, 1, 1), zero=0,
                            memory_budget=model.OPTIMIZER_BYTES * one_b.params() - 1))
    assert "optimizer" in message, (
        "the refusal of a budget under the optimizer line does not name the "
        "line: %r" % (message,))

    message = _refuses(
        model.ModelError, "an expert axis on a dense model",
        lambda: s.configure(tiny, full4, gpus=4, axes=(1, 1, 1, 4, 1)))
    assert "expert" in message, (
        "the refusal of ep=2 on a dense model does not name the experts: %r"
        % (message,))
    message = _refuses(
        model.ModelError, "a context axis the sequence does not divide",
        lambda: s.configure(tiny, full4, gpus=4, axes=(1, 1, 1, 1, 4), seq=3))
    assert "seq" in message or "split" in message, (
        "the refusal of a sequence the context axis cannot divide does not name "
        "seq or split: %r" % (message,))
    message = _refuses(
        fabric.FabricError, "a data-parallel group the ring cannot serve",
        lambda: s.configure(tiny, ring8, gpus=8, axes=(2, 4, 1, 1, 1),
                            memory_budget=ROOMY))
    assert message, "the refusal of an unservable group is empty"
    message = _refuses(
        model.ModelError, "a bucket that holds no bytes",
        lambda: s.configure(tiny, full4, gpus=4, bucket_bytes=0))
    assert "bucket" in message, (
        "the refusal of a zero-byte bucket does not name the bucket: %r"
        % (message,))
    message = _refuses(
        model.ModelError, "a wrap unit that holds no bytes",
        lambda: s.configure(one_b, full8, gpus=8, axes=(8, 1, 1, 1, 1), zero=3,
                            wrap_bytes=0))
    assert "wrap" in message, (
        "the refusal of a zero-byte wrap unit does not name the wrap: %r"
        % (message,))

    message = _refuses(
        model.ModelError, "a plan that is not a StepPlan",
        lambda: s.report(tiny, full4, "not a plan"))
    assert "plan" in message, (
        "the refusal of a report without a plan does not name plan: %r" % (message,))
    message = _refuses(
        model.ModelError, "a shape that is not a ModelShape",
        lambda: s.report("tiny", full4, s.configure(tiny, full4, gpus=4)[1]))
    assert "shape" in message, (
        "the refusal of a non-shape does not name shape: %r" % (message,))
    message = _refuses(
        fabric.FabricError, "a world that is not a fabric",
        lambda: s.report(tiny, "full4", s.configure(tiny, full4, gpus=4)[1]))
    assert "world" in message, (
        "the refusal of a non-fabric does not name world: %r" % (message,))

    print("check_10: the configuration — the axes multiply to the devices and "
          "the split is the argmin of stage 1's step_ticks over every candidate "
          "that fits, each axis larger than one contributing its own stage's "
          "collectives over its own ranks (dp's bucketed all-reduce sized on the "
          "local shard, the ZeRO ladder reproducing stages 3 and 4, tp's two "
          "all-reduces, the schedule's pp sends, ep's dispatch and "
          "combine, cp's KV ring) and one device the single-device reference, "
          "while report recomputes its numbers from the plan alone")

STAGES = [
    stage(
        1,
        file="stage_01.py",
        title="The shapes and the ledger",
        tags=["shapes", "ledger"],
        action="Write `Collective`, `StepPlan`, `MemoryLine`, `plan_bytes`, "
               "`network_bytes`, `plan_memory`, `plan_ticks`, `step_ticks` and "
               "`params_by_rank` in stage_01.py.",
        predict="How many bytes one parameter costs through a training step "
                "(params, gradients, optimizer state and masters), and what a "
                "rank holds when the parameter set does not divide the world "
                "evenly.",
        check=check_1,
    ),
    stage(
        2,
        file="stage_02.py",
        title="Data parallel",
        tags=["dp", "buckets"],
        action="Write `data_parallel` and `bucket_schedule` in stage_02.py.",
        predict="How many buckets a 1B model's gradients make at 25 MB each, "
                "what the all-reduce moves per rank for eight of them, and what "
                "the step costs when the communication hides behind the compute.",
        check=check_2,
    ),
    stage(
        3,
        file="stage_03.py",
        title="ZeRO-1 / ZeRO-2",
        tags=["zero", "sharding"],
        action="Write `shard_partition`, `assemble` and `zero` in stage_03.py.",
        predict="What 16 bytes per parameter becomes for eight ranks at ZeRO-1 "
                "and at ZeRO-2, and where the remainder of a state that does "
                "not divide the world goes.",
        check=check_3,
    ),
    stage(
        4,
        file="stage_04.py",
        title="ZeRO-3 / FSDP",
        tags=["fsdp", "wrap"],
        action="Write `wrap_policy`, `fully_sharded` and `in_flight` in "
               "stage_04.py.",
        predict="What a fully sharded step moves per rank and per layer, and "
                "where the peak memory happens while a layer's parameters are "
                "being gathered.",
        check=check_4,
    ),
    stage(
        5,
        file="stage_05.py",
        title="Tensor parallel",
        tags=["tp", "f/g"],
        action="Write `column_parallel`, `row_parallel`, `f`, `g` and "
               "`tensor_parallel` in stage_05.py.",
        predict="Why a column-then-row block needs one all-reduce in the "
                "forward and one in the backward, and how the composition lands "
                "on the single-device result.",
        check=check_5,
    ),
    stage(
        6,
        file="stage_06.py",
        title="Pipeline parallel",
        tags=["pp", "bubbles"],
        action="Write `gpipe`, `one_f_one_b`, `bubble`, `bubble_fraction` and "
               "`replay` in stage_06.py.",
        predict="Where the idle stages are in a (4, 8) schedule, and why "
                "1F1B's bubble is smaller than GPipe's for the same stages and "
                "micro-batches.",
        check=check_6,
    ),
    stage(
        7,
        file="stage_07.py",
        title="Pipeline schedules",
        tags=["schedules", "memory"],
        action="Write `interleaved`, `lifetime` and `in_flight` in "
               "stage_07.py.",
        predict="How virtual stages change the bubble, and how many "
                "activations can be alive at once when a buffer is reused.",
        check=check_7,
    ),
    stage(
        8,
        file="stage_08.py",
        title="Expert parallel",
        tags=["moe", "all-to-all"],
        action="Write `routing`, `dropped`, `balance_loss` and "
               "`expert_parallel` in stage_08.py.",
        predict="What a hot expert does to the dispatch's price, and how many "
                "tokens the capacity cap drops.",
        check=check_8,
    ),
    stage(
        9,
        file="stage_09.py",
        title="Sequence / context parallel",
        tags=["cp", "ring attention"],
        action="Write `online_attention` and `context_parallel` in "
               "stage_09.py.",
        predict="What a rank must keep to combine the blocks it has seen so "
                "far, and what the KV exchange costs per hop.",
        check=check_9,
    ),
    stage(
        10,
        file="stage_10.py",
        title="The configuration",
        tags=["config", "report"],
        action="Write `configure` and `report` in stage_10.py.",
        predict="For eight devices and a 1B model, which split of (dp, tp, pp, "
                "ep, cp) ticks least, and which of them does not fit in memory "
                "at all.",
        check=check_10,
    ),
]
