# Stage 7: the sandbox: a root the tools cannot leave

**Course:** Agents From Scratch (`agents-from-scratch`)
**File:** `stage_07.py`
**Tags:** sandbox, security

## The mechanism

Implement resolve_path and Sandbox: resolve, then compare, then act — with a read-only mode and the three tools.

## Tests

The tester runs your code like this:

```bash
forja test agents-from-scratch --stage 7
# same as:
python3 codecraft/cli.py run agents-from-scratch --stage 7
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> The root is /tmp/ws and the request is ../ws-evil/evil.txt: inside or outside?

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Notes

- the decision is made on the resolved path, never on the string that came in
- startswith compares characters; 'inside' is a question about path components
- read-only is a property of the sandbox, so the tool's fn inherits it

## Next

When this stage is green:

```bash
forja stage agents-from-scratch 8
```
