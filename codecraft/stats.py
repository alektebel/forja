"""How big each stage's tester is: measured, and recorded here on purpose.

`codecraft stage <course> [n]` prints the page a stage deserves before a line of
it is written: the file, what you implement, what the tester will do to it, and
how big that tester is. Two numbers, and only one of them can be recomputed:

  tests    the `assert` statements and explicit `raise`s inside the stage's
           check — the ways that check can reject your file. Always recomputable
           from `<course>/course.py`, which is why it is safe to record it. A
           course whose checks are written around a helper that refuses with an
           `AssertionError` of its own (`tcp-ip-from-scratch`'s `_refuses`) counts
           those calls too: they are the same rejection, spelled once instead of
           twenty times.
  mutants  the planted mistakes the stage's development harness proved the check
           catches. Each one is a wrong implementation the check must notice,
           and the harness that plants them lives *outside* this repository: it
           is built while a course is authored and cleaned up once the course is
           assembled. For the twelve courses below the harnesses still exist and
           the number is exact; for the other ten it is recoverable nowhere, and
           `None` says so instead of pretending a zero.

The pair is the honest answer to "how much does this stage test me": `tests` is
what the check says about itself, `mutants` is what it was proven to catch.

Measured 2026-10-16 against the twenty-two courses that carry a `course.py`. A check
that changes invalidates its row: re-measure with the course's harness
(`mutate_all.py <stage>` prints the caught and missed counts) and fix the tuple.
"""

# course slug -> [(tests, mutants), ...] in stage order, None where unmeasured.
STAGES = {
    "autograd-from-scratch": [
        (119, None), (108, None), (155, None), (68, None), (101, None),
        (95, None), (114, None), (101, None), (46, None), (77, None)],
    "rag-from-scratch": [
        (7, None), (5, None), (4, None), (5, None), (4, None), (5, None),
        (3, None), (5, None), (3, None)],
    "vector-index-from-scratch": [
        (20, None), (14, None), (15, None), (17, None), (18, None),
        (22, None), (13, None), (15, None), (11, None), (15, None)],
    "evals-from-scratch": [
        (16, None), (18, None), (23, None), (17, None), (14, None),
        (14, None), (20, None), (17, None), (16, None), (20, None)],
    "agents-from-scratch": [
        (30, None), (40, None), (81, None), (33, None), (38, None),
        (1, None), (2, None), (30, None), (57, None), (37, None)],
    "mcp-from-scratch": [
        (35, None), (46, None), (53, None), (98, None), (44, None),
        (3, None), (2, None), (40, None), (88, None), (58, None)],
    "agent-harness-from-scratch": [
        (17, None), (1, None), (30, None), (3, None), (2, None),
        (38, None), (6, None), (3, None), (29, None), (56, None)],
    "benchmark-from-scratch": [
        (22, None), (38, None), (44, None), (34, None), (27, None),
        (40, None), (24, None), (32, None), (40, None), (22, None)],
    "eval-framework-from-scratch": [
        (27, None), (29, None), (53, None), (34, None), (40, None),
        (51, None), (33, None), (43, None), (44, None), (53, None)],
    "cpu-from-scratch": [
        (66, None), (28, None), (39, None), (30, None), (39, None),
        (85, None), (60, None), (47, None), (50, None), (42, None)],
    "os-from-scratch": [
        (53, 35), (97, 49), (100, 59), (127, 62), (93, 69),
        (116, 81), (103, 62), (103, 60), (177, 113), (141, 51)],
    "distributed-training-from-scratch": [
        (46, 49), (69, 57), (89, 60), (83, 54), (45, 54),
        (50, 46), (41, 46), (88, 59), (39, 45), (114, 84)],
    "interconnects-from-scratch": [
        (47, 46), (37, 40), (83, 37), (27, 42), (66, 47),
        (55, 43), (57, 43), (54, 38), (86, 47), (91, 55)],
    "queue-and-workers-from-scratch": [
        (26, 38), (59, 40), (28, 33), (74, 40), (47, 40),
        (56, 40), (92, 40), (59, 39), (90, 40), (56, 36)],
    "orchestration-from-scratch": [
        (77, 51), (71, 47), (62, 46), (58, 70), (60, 49),
        (54, 40), (45, 48), (78, 49), (34, 64), (84, 62)],
    "durable-execution-from-scratch": [
        (77, 49), (71, 14), (77, 49), (83, 60), (85, 56),
        (52, 55), (66, 62), (102, 83), (58, 55), (97, 47)],
    "sandbox-capabilities-from-scratch": [
        (68, 48), (75, 54), (55, 39), (83, 42), (71, 50),
        (72, 60), (62, 54), (113, 51), (79, 53), (62, 43)],
    "agent-metrics-from-scratch": [
        (75, 43), (50, 40), (51, 45), (47, 47), (43, 49),
        (41, 47), (48, 39), (89, 67), (92, 61), (115, 72)],
    "tcp-ip-from-scratch": [
        (95, 42), (109, 57), (169, 70), (123, 64), (174, 77),
        (112, 57), (65, 43), (82, 46), (129, 58), (71, 40)],
    "concurrent-servers-from-scratch": [
        (133, 64), (72, 60), (138, 89), (88, 61), (110, 70),
        (91, 84), (114, 90), (114, 71), (174, 118), (71, 50)],
    "mqtt-broker-from-scratch": [
        (72, 43), (106, 69), (81, 44), (80, 63), (123, 66),
        (151, 67), (95, 58), (131, 86), (60, 64), (85, 40)],
    # Measured 2026-10-16 from the assembled `course.py` with the same recipe the
    # rows above follow (asserts + explicit raises + refusal calls + the two
    # rejections inside the shared helper), re-derived against L2's, mqtt's,
    # rag's and agents' recorded rows before it was applied; the mutants are the
    # `.fde-dev` harness's sweep, `mutate_all.py <stage>`, all twelve green.
    "fde-from-scratch": [
        (158, 87), (122, 78), (107, 76), (131, 65), (155, 77),
        (112, 67), (106, 74), (116, 68), (66, 54), (76, 75),
        (122, 79), (106, 84)],
}


def for_course(name):
    """{stage id: (tests, mutants)} for one course; empty when not measured."""
    return {i + 1: pair for i, pair in enumerate(STAGES.get(name, []))}


def totals(name):
    """(stages, tests, mutants) for one course, mutants summed over measured ones."""
    rows = STAGES.get(name, [])
    return (len(rows),
            sum(pair[0] for pair in rows),
            sum(pair[1] for pair in rows if pair[1] is not None))
