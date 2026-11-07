# Stage 35: SG stateful vs NACL stateless, same rules

**Course:** AWS From Scratch (`aws-from-scratch`)
**File:** `vpc.py`
**Tags:** networking

## The mechanism

NACL rules evaluate in NUMBER order, first match wins: a deny at 100 shadows an allow at 200. Security groups have no deny — absence of an allow IS the deny.

## Why the requirement is what it is

Two more points on the same design axis: NACL buys explicit ordering (and pays with statelessness); SG buys simplicity (and cannot express deny). Neither is strictly better — they answer different questions.


## Tests

The tester runs your code like this:

```bash
forja test aws-from-scratch --stage 35
# same as:
python3 codecraft/cli.py run aws-from-scratch --stage 35
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> SSH from 10.0.5.5 against deny-100/allow-200 rules.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage aws-from-scratch 36
```
