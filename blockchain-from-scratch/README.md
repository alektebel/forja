# Blockchain From Scratch

A ledger as a hash chain plus a rule for who appends — ten graded stages building a blockchain from first principles: block headers and the digest that seals them, Merkle trees and inclusion proofs, addresses and signatures, the UTXO set and the spend, the mempool and the double-spend, proof-of-work's target and difficulty adjustment, proof-of-stake's slots and attestations, fork choice, the network of peers, and convergence — where every simulated peer lands on the world's own answer key.

Every number is an integer; no float, no math, no random, no clock, no socket, no thread, no subprocess.  Every "time" is a tick.  Refusals name their offender.

## The world is provided, the stages are yours

`ledger.py`, `keys.py` and `net.py` are the world, and they are **read-only**: the world is deterministic, and a check can run any world function twice and get the same answer.  The world exposes accessors that serve as the answer key — a stage must reproduce, not read.

| File | What it holds |
|---|---|
| `ledger.py` | Hashing (`digest`, `canonical`, `_hash_bytes`), a deterministic SplitMix64 PRNG (`prng`), block/header/transaction/output record constructors, constants (`COIN`, `RETARGET_INTERVAL`, `TICKS_PER_BLOCK`, `GENESIS_HASH`, `MAX_TARGET`), and the `LedgerError` refusal family |
| `keys.py` | Toy Schnorr signatures over a 61-bit Mersenne prime (`P = 2^61 - 1`): `keygen`, `pubkey`, `sign`, `verify`, `address` |
| `net.py` | Five-peer roster (`alpha`..`epsilon`), deterministic delivery log, scenario generation, network message delivery, and the honest answer key |

## How this course is verified

| What | Command | Result |
|---|---|---|
| template mode | `python3 course.py` (each `check_N`) | 10/10 raise `NotImplementedError` |
| solutions mode | copy solutions over templates, then run checks | 10/10 PASS |
| mutation battery | see solutions/mutate_blockchain.py | MISSED: 0 |

## The laws a stage is held to

- Standard library only, `hashlib` permitted, no `float`, no `math`, no `random`, no clock, no socket, no thread, no subprocess.
- A stage imports the world and its own stage file only, never a later one.
- No module-level mutable state; the world is never written.
- A shape mismatch raises (``LedgerError``, ``BlockError``, ``MerkleError``, etc.), naming the offender; a verdict is returned.
- The first docstring paragraph is the stage's own title line, every public function is a docstring plus exactly one ``raise NotImplementedError``, and the file carries its ``DESIGN DECISION`` blocks and a ``TODO: implement`` line.
- Every check ends with a run-twice determinism proof.

## Running it

```bash
python3 codecraft/cli.py run blockchain-from-scratch
```

## Limits

The world does **not** model: real-world block sizes, real difficulty targets, full transaction serialization, mempool eviction strategies beyond fee replacement, real-world fork resolution rules beyond honest weight, Byzantine faults beyond the single planted fork, gas or computational limits on signatures, or any networking protocol beyond the fixed delivery log.  These are the boundaries of this teaching version.