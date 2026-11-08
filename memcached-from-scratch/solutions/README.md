# Solutions

Finished, runnable versions of each stage. Read them *after* attempting — a
solution read cold is just more prose.

| File | Stage |
|---|---|
| `stage_01.py` | The ring, and the hash that must not move |
| `stage_02.py` | Slab classes, and the size that does not fit |
| `stage_03.py` | Per-page LRU, and the hot key that dies |
| `stage_04.py` | The ASCII protocol, byte-exact |
| `stage_05.py` | Tail tolerance, paying latency in queries |
| `stage_06.py` | Statistical herding, spread over ticks |
| `stage_07.py` | Single-flight, and why the mutex alone loses to the wide wave |
| `stage_08.py` | Backup replication and the warm restart |
| `stage_09.py` | The report, and the rates that must be derived |
| `stage_10.py` | The capstone, two runs, one byte string |

Stages 5–10 build on the earlier ones (`stage_08` routes through `stage_01`'s
ring into `stage_03`'s stores, `stage_10` imports `stage_01`, `stage_03` and
`stage_07` and runs all of it), so copying one over its template needs the
earlier ones in place too — which the course root always has.

To compare a stage, copy it over the template and re-run the checker, then
restore the template if you want to try again:

```bash
cp solutions/stage_07.py stage_07.py
python3 codecraft/cli.py run memcached-from-scratch
```

All ten pass their checks with the standard library alone: no threads, no
asyncio, no wall clock, no `random`, and no `hash()` — every count is an int
off an injected clock, which is what lets a check assert the numbers a run
produced instead of timing it.

## What each demo prints

Every solution is runnable standalone from the course root
(`PYTHONPATH=. python3 solutions/stage_NN.py`). These are the actual outputs.

**stage_01 — 150 vnodes vs one point per node, and what a death costs:**

```text
9 nodes, 90k keys: ideal 10000/node, worst deviation 886 (8.9%)
same ring with 1 vnode/node: worst deviation 14980 (149.8%)
dropping 1 of 9 nodes moved 9947 keys (11.1%; mod-9 hashing moves ~89%)
```

**stage_02 — the ladder, a hole reused, the ceiling refusing:**

```text
ladder: (8, 16, 32, 64)
user:1 (10B) -> Slot(cls=16, page=0, index=0)  user:2 (5B) -> Slot(cls=8, page=0, index=0)
refused: item of 65 bytes does not fit: the max class is 64 and a value is never split
after a removal, user:3 (30B) -> Slot(cls=32, page=0, index=0)
stats: {'pages': {8: 1, 16: 1, 32: 1, 64: 0}, 'granted': {8: 1, 16: 1, 32: 1, 64: 0}, 'free': {8: 0, 16: 1, 32: 0, 64: 0}}
```

**stage_03 — the hot key buried with its page, neighbours and all:**

```text
died with the page: ['p1:a', 'p1:b']
hot key evicted by its own page: True
stats: {'pages': {1: 2}, 'live': 3, 'evicted_pages': 2, 'evicted_items': 4, 'expired_freed': 0}
expiry read before: True | after: True | slot freed: True
```

**stage_04 — byte-exact responses, chunk refused before the store:**

```text
'STORED\r\n'
'VALUE user:1 0 5\r\nalice\r\nEND\r\n'
'VALUE user:1 0 5 1\r\nalice\r\nEND\r\n'
'CLIENT_ERROR bad data chunk\r\n'
'NOT_STORED\r\n'
'STORED\r\n'
'EXISTS\r\n'
'STORED\r\n'
'9\r\n'
'0\r\n'
'DELETED\r\n'
'END\r\n'
'STAT pid 1\r\nSTAT version 1.5.32-scratch\r\nSTAT curr_items 1\r\nSTAT evictions 0\r\nSTAT expired_unfetched 0\r\nSTAT get_hits 2\r\nSTAT get_misses 1\r\nSTAT cmd_total 13\r\nEND\r\n'
```

**stage_05 — the tail bought with queries, 62 reads for 62 chances:**

```text
plain:    worst 29ms, mean 9.3ms, origin queries 600
tailcut:  worst 29ms, mean 8.0ms, origin queries 662 (62 backups sent, 56 won)
```

**stage_06 — the column thins, the total does not move, and the expensive
key herds *less*:**

```text
no window                  total 2000  spike 1000  early    0  at_death 1000
window, cheap rebuild      total 2000  spike  150  early 1000  at_death    0
window, expensive rebuild  total 2000  spike  672  early  328  at_death  672
```

**stage_07 — depth vs width, and the defence that only knows one of them:**

```text
== cold wave (depth): 10 clients x 20 keys, one tick, 30-tick rebuilds ==
none           origin  200  busy 6000  waits   0  early   0  peak/tick  200
mutex          origin   20  busy  600  waits 180  early   0  peak/tick   20
== expiry wave (width): 10 frontends x 20 keys, die at tick 50 ==
none           origin  400  column@death  200  peak other tick  200
mutex          origin  400  column@death  200  peak other tick  200
herding        origin  400  column@death    0  peak other tick   45
mutex+herding  origin  400  column@death    0  peak other tick   45
```

**stage_08 — zero queries across the crash, silence across the restart:**

```text
plain cache    warm  90 | crash of 1 of 3 nodes:  28 origin queries
replicated     warm  90 | crash of 1 of 3 nodes:   0 origin queries
restart:    0 origin queries across the returning node |  28 reads rescued by a backup | 112 copies refilled |  56 items live on it
```

**stage_09 — every number derived, nothing stored:**

```text
{"curr_items": 6, "evictions": 0, "expired_freed": 0, "get_hits": 9, "get_misses": 1, "hit_rate": 0.9, "pages": 2, "sets": 6, "uptime": 100}
```

**stage_10 — two runs, one byte string:**

```text
rows: 744 | two runs identical: True
digest: 1a8e93c17be92c60
{"busy":60,"caches":[["fe-00",31,11,40],["fe-01",35,7,40],["fe-02",35,7,40],["fe-03",29,13,40]],"node_hits":[["n1",49],["n2",56],["n3",35]],"origin_queries":20}
```

The full digest is
`1a8e93c17be92c60e573add8bbd8cc0a3be0b288d35670860a6905b250abcf06`, and the
report's conservation is what the capstone check pins: the frontends issued
40+40+40+40 = 160 rebuilds, and they were answered 20 times at the origin and
140 times by the node tier.
