# Solutions

Finished, runnable versions of each stage. Read them *after* attempting — a
solution read cold is just more prose.

| File | Stage |
|---|---|
| `stage_01.py` | The word and the flags: a mask, a sign, a 14-bit immediate, and carry versus signed overflow |
| `stage_02.py` | The decoder: fields from their own shifts, unused fields cleared, `decode`/`encode` round-tripping |
| `stage_03.py` | The register file: `r0` hardwired, snapshots that are copies, a restore that takes exactly sixteen |
| `stage_04.py` | The ALU: truncating division, the dividend's remainder, `sra` on the signed value, two fault kinds |
| `stage_05.py` | Memory: bounds and alignment before anything is written, little-endian sizes 1/2/4, snapshots as bytes |
| `stage_06.py` | The machine: fetch, decode, execute, a trace of effects, and a fault that is data |
| `stage_07.py` | The loader and the record: a name or a source, `(pc, word)` steps, a fingerprint of the architectural state |
| `stage_08.py` | The five-stage pipeline that stalls, squashes and still retires the machine's exact trace |
| `stage_09.py` | The forwarding pipeline: MEM and WB paths, the one-cycle load-use stall, the branch flush |
| `stage_10.py` | The measurement: CPI and speedup as rounded floats, and equivalence as a fingerprint comparison |

The stages are cumulative in the way the course is: stage 2 imports stage 1's
`sign_extend`, stage 3 its `word`, stage 4 its `Flags` and flag algebra, stage 5
its byte helpers, stage 6 imports stages 2, 3, 4 and 5 (the machine *is* those
parts), stage 7 imports stage 6's `Machine`, stage 8 imports stages 2 to 6,
stage 9 imports stage 8's `Pipeline` and `STAGES`, and stage 10 measures stages 6,
8 and 9 against each other through stage 7's `load` and `fingerprint`. So copying
one solution over its template needs its neighbours in place too, and `isa.py` is
not a stage: it is the instruction set, the assembler and the five programs,
provided complete.

To compare a stage, copy it over the template and re-run the checker, then
restore the template if you want to try again:

```bash
cp solutions/stage_09.py stage_09.py
python3 codecraft/cli.py run cpu-from-scratch
```

All ten pass their checks with the standard library alone. Four are worth reading
even if you solved them: `stage_04.alu` is where Python's idea of division has to
be abandoned (`//` floors, hardware truncates; `%` takes the divisor's sign, the
ISA takes the dividend's); `stage_06.step` is the one function that decides what
a fault *is* — a recorded end state, not an exception — and it is also the
function the whole course compares against; `stage_08.step_pipeline` is where the
retire-first ordering, the squash and the stall accounting produce
`cycles == retired + 4 + stalls_total`; and `stage_09.forward_operands` is the
two instructions' worth of wiring that makes the load-use stall the *only* one
left, with the stall charged exactly once, in the right slot.
