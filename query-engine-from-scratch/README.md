# Query Engine From Scratch

Build a query engine over a provided storage floor — in pure standard-library
Python, with no floats, no clock, and no threads.

A database is a file format plus a promise about what a query returns. The
format is provided; the promise is the exercise. A parse that refuses five
malformations instead of guessing; a resolve against a catalog that may lie; a
predicate pushed where it is earned rather than left where it was written; a
B+tree that splits when the leaf is full; a plan whose arithmetic — matched rows
against a quarter of the table — decides scan versus index, and can explain
itself in one line; an executor of iterators over pages whose answer's order is
part of the answer; a buffer that pins what a join still needs and evicts what
it does not; a commit that is one buffered byte and a barrier, not a hope; a
recovery that redoes the committed, undoes the rest, and counts a torn record
rather than trusting it; and a proof — a hundred queries through the whole
stack, each on a fresh world so the page count is the query's own receipt, with
an audit that re-reads the proof against the world and names the ids that
failed.

The domain is provided (`disk.py`, `pages.py`, `tables.py`, `ops.py`): a disk
whose writes land in a buffer and whose reads see only the durable image, one
barrier for durability, and a `power_fail(tear=…)` that tears the last buffered
write; a pager with a shadow, an allocate/free freelist, and the record format's
law; four tables, one index, a catalog with a fixture where it lies, a hundred
pinned queries, the plan facts, and a crash schedule of four fixtures. The
engine is what you write.

No `open(2)` behind the disk, no real fsync behind the barrier: the crash
schedule is deterministic, the torn write is a record the device keeps, and
`disk.counters()` is the ledger every durability claim has to survive.
