# Stage 2: the tools the model can see

**Course:** Agents From Scratch (`agents-from-scratch`)
**File:** `stage_02.py`
**Tags:** tools, schemas

## The mechanism

Implement tool, describe and validate: an object schema per tool, a description list for the prompt, and argument validation that names the offending key.

## Tests

The tester runs your code like this:

```bash
forja test agents-from-scratch --stage 2
# same as:
python3 codecraft/cli.py run agents-from-scratch --stage 2
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> The schema declares lines as an integer and the model sends "lines": true: does the tool run?

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Notes

- isinstance(True, int) is True in Python, and a boolean is not an integer
- a numeric string is how a model spells a number
- a default belongs to the declaration, and is copied into every call, never shared

## Next

When this stage is green:

```bash
forja stage agents-from-scratch 3
```
