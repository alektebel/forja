# Stage 2: deterministic training and compression

**Course:** LLM From Scratch (`llm-from-scratch`)
**File:** `tokenizer.py`
**Tags:** determinism, ordering

## The mechanism

In train_bpe, take the most frequent pair but break ties by the smallest pair, and start new ids at 256. Determinism is the whole point — same corpus, same table.

## Tests

The tester runs your code like this:

```bash
forja test llm-from-scratch --stage 2
# same as:
python3 codecraft/cli.py run llm-from-scratch --stage 2
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> Train twice on one corpus: identical merge table?

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage llm-from-scratch 3
```
