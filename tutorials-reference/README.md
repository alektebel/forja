# Tutorials reference — recovered from `build-your-own-x`

Recovered 2026-10-18 from the index at `github.com/codecrafters-io/build-your-own-x`
(kept whole as `../codecrafters-reference/build-your-own-x-index.md`): the
tutorials this repository's pending rows need, copied whole so the contract of
each course starts from someone else's worked example instead of a blank page.
Licensing: each piece keeps its upstream license ( Crafting Interpreters is
CC BY-NC-ND 4.0 with code under MIT; mal is MIT; the 500 Lines chapters are
CC BY 4.0 — they are here as **reading**, and no stage's solution copies them).

## What is here, and which row it feeds

| Directory | What it is | Feeds |
|---|---|---|
| `crafting-interpreters/` | Four chapters of Bob Nystrom's *Crafting Interpreters* Part II as Markdown: chunks of bytecode, the bytecode VM, calls and functions, closures — plus the full **garbage collection** chapter (reachability, mark-sweep with the tri-colour abstraction, `markRoots`/`traceReferences`/`sweep`, and the write-barrier problem named before it is solved) | **G8 `runtime-from-scratch`** — the VM chapters are the shape of the stack machine and frames; the GC chapter is the reading half of stages 4–8 |
| `babys-first-gc/article.html` | Bob Nystrom's *Baby's First Garbage Collector*: mark-sweep over pairs in ~100 lines, with the exact invariant this course makes checkable — nothing reachable is ever freed | **G8** — the reference implementation a stage 4 solution is measured against in spirit, never copied from |
| `byterun/` | Allison Kaptur & Ned Batchelder's **Byterun**, a Python interpreter in Python (the *500 Lines* chapter's code): the frame stack, the block stack, why `RETURN_VALUE` pops through blocks — the closest thing to a working model of CPython's loop | **G8** stages 1–3 (dispatch, frames, step accounting) and the "Python interpreter written in Python" lineage the course cites |
| `mal-python3/` | the **Python 3 implementation of mal** (Make a Lisp): reader, printer, eval with TCO, atoms, functions — 13 steps from `step1_read_print.py` to `stepA_mal.py` | **G8** as a second opinion on interpreter layering, and any future Lisp row |
| `dbdb/` | **DBDB** (Dog Bed Database, *500 Lines*): a key/value store layered binary tree (logical) over an address-ordered storage (physical) over a file — the layering where a crash between the two is the whole lesson, and the root address is committed last | **L5 `redis-from-scratch`** (persistence half) and **A5**'s storage story |
| `lc3-vm/` | Justin Meiners' *Write your Own Virtual Machine* (LC-3): the register file, the fetch-decode-execute loop, memory-mapped IO, trap routines — C, but the discipline (one dispatch per step, a closed opcode vocabulary) is the course's own | **G8** (the step-accounting model) and G3's ISA reading |

| `cache-lite/` | kezhenxu94's **cache-lite** (Kotlin): one `GenericCache` interface over LRUCache/FIFOCache/ExpirableCache/Weak/Soft/Perpetual — the eviction-policy zoo as implementations of one contract, exactly the shape of system-design's cache module | **A5 `system-design`** (the cache/TTL modules) |
| `write-a-hash-table/` | James Routley's **write-a-hash-table** in C, seven chapters: the struct, the hash function, open addressing with tombstones, the API, resizing — the mistake catalogue (delete leaves a tombstone, not a hole) is the lesson | **A5 `system-design`** (consistent hashing builds on it) |
| `kafka-like-java/` | a **Kafka-like system in Java, staged 1–7** (protocol, zookeeper, storage, broker, client, producer/consumer APIs): the partition as an append-only log with an offset cursor, in worked code | **L6 `kafka-from-scratch`** — the second opinion beside the 25-stage CodeCrafters corpus |
| `docker-mocker/` | Tony Baloney's **mocker**: a proof-of-concept Docker in pure Python — namespaces via `unshare`, cgroups v2, an overlayfs root, `pull`/`run`/`exec` as subprocess plumbing | **D-row candidate** `docker-from-scratch` — the Python end of the Linux-container mechanism, beside the 6-stage CodeCrafters corpus (`codecrafters-reference/docker/`) |
| `docker-bocker/` | **bocker**: Docker in ~100 lines of bash — the same mechanism with nothing hidden: chroot, a network namespace, overlayfs mounts, and the API calls behind `bocker pull/run` | **D-row candidate** — the least code that still deserves the name |
| `chip8-python/` | craigthomas' **Chip8Python**: a CHIP-8/Super-Chip emulator in Python — the decode dispatch over a closed opcode vocabulary, a display as a bitmap the emulator owns, the timers driven by a stepped clock | **D-row candidate** `emulator-from-scratch` (CHIP-8 first, Game Boy the second half), with the LC-3 tutorial beside it |
| `rl-qlearning/` | **RL-from-zero**: tabular Q-learning in Python on gymnasium, staged (agent, replay, target, main), numpy + gymnasium only | **D-row candidate** `rl-control-from-scratch` — a provided world (a deterministic gridworld/MDP the course writes) with Q-learning, SARSA and policy iteration as the ladder |


## The rule, same as `codecrafters-reference/`

These are **source material, not answers**: a stage's solution is written from
the provided world and the frozen contract, and a check that catches a planted
mutation proves it. What a tutorial gives the contract is the *order* (the
ladder), the *invariants worth checking* (reachability, the forwarding
pointer, the committed root), and the *mistake catalogue* (what each author
got wrong first).
