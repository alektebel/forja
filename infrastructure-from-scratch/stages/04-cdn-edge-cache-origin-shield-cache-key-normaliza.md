# Stage 4: CDN — edge cache, origin shield, cache-key normalization

**Course:** Infrastructure From Scratch (`infrastructure-from-scratch`)
**File:** `cdn_caching.py`
**Tags:** moderate, caching, http

## The mechanism

Implement EdgeCache honouring Cache-Control (private/no-store/max-age, surrogate keys, purge_by_key), OriginShield collapsing concurrent origin fetches, and normalize_cache_key.

## Tests

The tester runs your code like this:

```bash
forja test infrastructure-from-scratch --stage 4
# same as:
python3 codecraft/cli.py run infrastructure-from-scratch --stage 4
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> two objects sharing a surrogate key — how many does one purge remove?

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Notes

- parse directives into a dict, then branch on no-store/private
- shield: per-key lock, first thread fetches, rest read its result
- normalize: strip tracking params, sort what remains

## Next

When this stage is green:

```bash
forja stage infrastructure-from-scratch 5
```
