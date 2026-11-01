# Stage 1: URL shortener — base62 codes, TTL store, click stats

**Course:** Infrastructure From Scratch (`infrastructure-from-scratch`)
**File:** `url_shortener.py`
**Tags:** simple, encoding, storage

## The mechanism

Implement base62 encode/decode, a URLStore with TTL expiry and hit stats, and a URLShortener that mints codes and resolves them.

## Tests

The tester runs your code like this:

```bash
forja test infrastructure-from-scratch --stage 1
# same as:
python3 codecraft/cli.py run infrastructure-from-scratch --stage 1
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> why must the code counter advance before encoding, never after?

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Notes

- digits = 0-9, A-Z, a-z; 62 becomes '10', not a new digit
- expiry: compare the saved timestamp on read, drop lazily
- shorten() must be collision-free: counter ids never repeat

## Next

When this stage is green:

```bash
forja stage infrastructure-from-scratch 2
```
