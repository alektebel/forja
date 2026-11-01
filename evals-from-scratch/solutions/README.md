# Solutions

Finished, runnable versions of each stage. Read them *after* attempting — a
solution read cold is just more prose, and these are short enough to fool you
into thinking the stage was easy.

| File | Stage |
|---|---|
| `stage_01.py` | The eval set, and the split that must not leak |
| `stage_02.py` | The numbers that are not about quality |
| `stage_03.py` | Deterministic assertions |
| `stage_04.py` | Exact match and token F1 |
| `stage_05.py` | Ranking metrics, and the ideal that is not ideal |
| `stage_06.py` | The judge, and the order you showed it in |
| `stage_07.py` | What the judge is worth |
| `stage_08.py` | Is the difference real? |
| `stage_09.py` | Ten configs, one winner, no correction |
| `stage_10.py` | The gate, and the report you can diff |
| `stage_11.py` | Fields, not strings |
| `stage_12.py` | Confidence that earns its name |
| `stage_13.py` | The score that moves when the prompt's clothes move |

Stages 6–10 build on the earlier ones (`stage_10` imports `stage_08` for the
paired bootstrap); 11–13 are self-contained but assume you already care about
what a gate and a metric *mean*. Copying one over its template needs the
earlier ones in place if you re-run the whole course.

```bash
cp solutions/stage_11.py stage_11.py
python3 codecraft/cli.py run evals-from-scratch --stage 11
```

All thirteen pass their checks with the standard library alone. Worth reading
even if you solved them: `stage_08.paired_bootstrap`, `stage_10.gate`,
`stage_11.macro_f1` (why micro lies), and `stage_12.ece` (why unweighted bins
lie).
