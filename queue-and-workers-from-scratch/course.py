"""Course manifest — read codecraft/api.py for the full shape.

TITLE / DESCRIPTION / LEVEL / ORDER are course metadata.
STAGES is the graded sequence; each stage names the file to implement, the
concept tags it exercises, the one micro-action when it fails, the number to
predict when it passes, and a `check` function that asserts the requirement.
"""

from codecraft.api import stage

TITLE = 'Queue & Workers From Scratch'
DESCRIPTION = 'Learn Queue & Workers From Scratch by building it from scratch.'
LEVEL = "custom"
ORDER = 99


def check_1():
    from stage_01 import solve
    result = solve()
    raise NotImplementedError(
        "course 'queue-and-workers-from-scratch': write the real assertions for stage 1 in course.py")
    assert result is not None, "replace this with a requirement that can fail"




def check_2():
    from stage_02 import solve
    result = solve()
    raise NotImplementedError(
        "course 'queue-and-workers-from-scratch': write the real assertions for stage 2 in course.py")
    assert result is not None, "replace this with a requirement that can fail"




def check_3():
    from stage_03 import solve
    result = solve()
    raise NotImplementedError(
        "course 'queue-and-workers-from-scratch': write the real assertions for stage 3 in course.py")
    assert result is not None, "replace this with a requirement that can fail"




def check_4():
    from stage_04 import solve
    result = solve()
    raise NotImplementedError(
        "course 'queue-and-workers-from-scratch': write the real assertions for stage 4 in course.py")
    assert result is not None, "replace this with a requirement that can fail"




def check_5():
    from stage_05 import solve
    result = solve()
    raise NotImplementedError(
        "course 'queue-and-workers-from-scratch': write the real assertions for stage 5 in course.py")
    assert result is not None, "replace this with a requirement that can fail"




def check_6():
    from stage_06 import solve
    result = solve()
    raise NotImplementedError(
        "course 'queue-and-workers-from-scratch': write the real assertions for stage 6 in course.py")
    assert result is not None, "replace this with a requirement that can fail"




def check_7():
    from stage_07 import solve
    result = solve()
    raise NotImplementedError(
        "course 'queue-and-workers-from-scratch': write the real assertions for stage 7 in course.py")
    assert result is not None, "replace this with a requirement that can fail"




def check_8():
    from stage_08 import solve
    result = solve()
    raise NotImplementedError(
        "course 'queue-and-workers-from-scratch': write the real assertions for stage 8 in course.py")
    assert result is not None, "replace this with a requirement that can fail"




def check_9():
    from stage_09 import solve
    result = solve()
    raise NotImplementedError(
        "course 'queue-and-workers-from-scratch': write the real assertions for stage 9 in course.py")
    assert result is not None, "replace this with a requirement that can fail"




def check_10():
    from stage_10 import solve
    result = solve()
    raise NotImplementedError(
        "course 'queue-and-workers-from-scratch': write the real assertions for stage 10 in course.py")
    assert result is not None, "replace this with a requirement that can fail"


STAGES = [
    stage(
        1,
        file="stage_01.py",
        title='stage 1 requirement',
        tags=[],
        action="State the one concrete thing to implement for stage 1.",
        predict="State the number or behaviour to predict before running.",
        check=check_1,
    ),
    stage(
        2,
        file="stage_02.py",
        title='stage 2 requirement',
        tags=[],
        action="State the one concrete thing to implement for stage 2.",
        predict="State the number or behaviour to predict before running.",
        check=check_2,
    ),
    stage(
        3,
        file="stage_03.py",
        title='stage 3 requirement',
        tags=[],
        action="State the one concrete thing to implement for stage 3.",
        predict="State the number or behaviour to predict before running.",
        check=check_3,
    ),
    stage(
        4,
        file="stage_04.py",
        title='stage 4 requirement',
        tags=[],
        action="State the one concrete thing to implement for stage 4.",
        predict="State the number or behaviour to predict before running.",
        check=check_4,
    ),
    stage(
        5,
        file="stage_05.py",
        title='stage 5 requirement',
        tags=[],
        action="State the one concrete thing to implement for stage 5.",
        predict="State the number or behaviour to predict before running.",
        check=check_5,
    ),
    stage(
        6,
        file="stage_06.py",
        title='stage 6 requirement',
        tags=[],
        action="State the one concrete thing to implement for stage 6.",
        predict="State the number or behaviour to predict before running.",
        check=check_6,
    ),
    stage(
        7,
        file="stage_07.py",
        title='stage 7 requirement',
        tags=[],
        action="State the one concrete thing to implement for stage 7.",
        predict="State the number or behaviour to predict before running.",
        check=check_7,
    ),
    stage(
        8,
        file="stage_08.py",
        title='stage 8 requirement',
        tags=[],
        action="State the one concrete thing to implement for stage 8.",
        predict="State the number or behaviour to predict before running.",
        check=check_8,
    ),
    stage(
        9,
        file="stage_09.py",
        title='stage 9 requirement',
        tags=[],
        action="State the one concrete thing to implement for stage 9.",
        predict="State the number or behaviour to predict before running.",
        check=check_9,
    ),
    stage(
        10,
        file="stage_10.py",
        title='stage 10 requirement',
        tags=[],
        action="State the one concrete thing to implement for stage 10.",
        predict="State the number or behaviour to predict before running.",
        check=check_10,
    ),
]
