# Stage 3: the toolbox: a failure is an observation

**Course:** Agents From Scratch (`agents-from-scratch`)
**File:** `stage_03.py`
**Tags:** tools, errors

## The mechanism

Implement ToolBox: registry order, validation through stage 2, a deterministic rendering of every result, and a head-preserving truncation.

## Tests

The tester runs your code like this:

```bash
forja test agents-from-scratch --stage 3
# same as:
python3 codecraft/cli.py run agents-from-scratch --stage 3
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> A tool raises ValueError('disk on fire'): what does the model see next, and does the run survive?

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Notes

- the content string is the model's whole world here: make it something it can act on
- truncate the head, because a tool reports its bad news at the end
- str(result) embeds an address for some objects, and then the transcript changes between runs

## Next

When this stage is green:

```bash
forja stage agents-from-scratch 4
```
