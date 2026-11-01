# Solutions

The finished version of each stage. Each file is a drop-in replacement for the
template with the same name: copy `solutions/stage_01.py` over `stage_01.py` to
see one stage pass, or compare function by function after your own attempt.

The stages build on one another — `stage_03.py` imports `stage_02.py`,
`stage_07.py` imports stages 2 through 6, and `stage_08.py` imports stages 1, 3,
4 and 7. If you are checking a late stage in isolation, copy the earlier
solutions too, or run the whole course after filling in the earlier templates.

The checks in `course.py` never import this directory. They only import the
templates at the course root, so a solution cannot pass a check by being
present.
