# Blockchain From Scratch — solutions

Each solution file implements the functions declared in its template.
Run with `python3 solutions/stage_NN.py` to see a small demo output.

| Stage | Demo output |
|---|---|
| `python3 solutions/stage_01.py` | Two-block chain: genesis seal and block 1 link |
| `python3 solutions/stage_02.py` | Merkle tree for 4 txs: leaf count, root, per-tx proofs |
| `python3 solutions/stage_03.py` | Keygen, address, sign, verify: all round-trip |
| `python3 solutions/stage_04.py` | UTXO set from one block: balance for alice and bob |
| `python3 solutions/stage_05.py` | Admit tx1, reject double-spend tx2, rank by fee |
| `python3 solutions/stage_06.py` | Mine a block (easy target), retarget with clamping |
| `python3 solutions/stage_07.py` | Proposer selection across 5 slots, one attestation |
| `python3 solutions/stage_08.py` | Fork choice: highest honest weight wins |
| `python3 solutions/stage_09.py` | Node receives a block: chain grows from 0 to 1 |
| `python3 solutions/stage_10.py` | Five nodes converge on one head |