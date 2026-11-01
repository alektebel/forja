# Stage 2: Consistent hashing — virtual-node ring, rendezvous

**Course:** Infrastructure From Scratch (`infrastructure-from-scratch`)
**File:** `consistent_hash.py`
**Tags:** simple, hashing, routing

## The mechanism

Implement HashRing with virtual nodes (add/remove/get_node/distribution/migration_count) and RendezvousHash.

## Tests

The tester runs your code like this:

```bash
forja test infrastructure-from-scratch --stage 2
# same as:
python3 codecraft/cli.py run infrastructure-from-scratch --stage 2
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> adding one node to an N-node ring — how many keys move?

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Notes

- bisect over sorted (position, node) pairs, wrap at the end
- virtual nodes: hash f'{node}#vnode{i}' 150 times per server
- rendezvous: score every node per key, take the max

## Next

When this stage is green:

```bash
forja stage infrastructure-from-scratch 3
```
