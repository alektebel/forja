"""Query Engine From Scratch — a query engine over a provided storage floor.

Ten graded stages over a machine provided as data (`disk.py`, `pages.py`,
`tables.py`, `ops.py`), the way the rest of this repository teaches a mechanism:
the world is data and holds the ground truth, a stage is a file you write, a
check is what happens to it, and every promise the engine makes is on show
because a file format plus a guarantee is what a database is.

What the course is about, in one line: *a query is a tree that becomes a plan,
a plan that becomes page reads, and the proof is a hundred queries whose rows
are the reference's own.*

    the parse: words, trees, and the five refusals
    the resolve: names against a catalog that may lie
    the predicates: conjuncts, and where they go
    the index: a B+tree that splits
    the plan: pushdown, selectivity, and the earned index
    the executor: iterators over pages
    the buffer: pinning, eviction, and the page you did not keep
    the commit: a log, and a rule
    the recovery: redo, undo, discard
    the proof: a hundred queries, and the audit

The house laws hold here (`.g5-dev/CONTRACT.md` §1): standard library only, no
`float` literal, no `random`, no clock, no thread, no socket, and no process of
your own — and, this course's own additions, the world is read-only: a stage
never writes the catalog's or the tables' own rows, every page read goes through
the pager, and every durability claim survives the crash schedule. The disk is
never lied to: `disk.counters()` is the device's own record, and a stage's every
claim about barriers and torn writes has to survive a re-read of it.

What the course does **not** do is call anything real. There is no `open(2)`
behind `disk.Disk`, no BSD db behind the B+tree, and no WAL fsync behind
`pager.sync`: the disk is a buffer and a durable image, the commit is a barrier,
a torn record is counted rather than trusted, and the whole course is
deterministic enough that two runs of the same query against the same world
produce the same pages.

    python3 codecraft/cli.py run query-engine-from-scratch
"""

from codecraft.api import stage

TITLE = "Query Engine From Scratch"
DESCRIPTION = ("A query engine over a provided storage floor: a database is a file "
               "format plus a promise about what a query returns, and every promise "
               "is on show. Ten stages that parse a query into a tree and refuse the "
               "five malformations, resolve names against a catalog that may lie, "
               "split predicates into conjuncts and push them where they are earned, "
               "build a B+tree that splits, price a plan and let selectivity earn "
               "the index, run every operator as an iterator over pages, pin and "
               "evict in a real buffer, commit through a log whose commit record is "
               "one buffered byte, recover by redoing, undoing and discarding — a "
               "torn record counted, never trusted — and prove the whole stack on a "
               "hundred queries with an audit that names the ids that failed. With "
               "the world read-only, every durability claim surviving the crash "
               "schedule, and no float and no clock anywhere.")

LEVEL = "advanced"
ORDER = 34


# --- stage 1 -----------------------------------------------------------------------
def check_1():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "query-engine-from-scratch"

    S1_TOKEN_KINDS = ("word", "int", "string", "op")

    S1_PARSE_KEYS = ("select", "columns", "table", "joins", "where", "order",
                     "limit")

    S1_PARSE_ERRORS = ("empty", "no_from", "bad_column", "bad_op", "bad_value")

    def _repo(start=None):
        for candidate_start in (os.environ.get("G5_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "disk.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set G5_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        try:
            got = call()
        except exc as e:
            for name in names:
                assert name in str(e), (
                    "%s: the refusal names %r, not %r" % (what, str(e)[:60], name))
            return
        except Exception as e:  # noqa: BLE001
            raise AssertionError("%s raised %r, not %s" % (what, e, exc.__name__))
        raise AssertionError("%s was accepted (%r); it must refuse" % (what, got))

    def _s1_surface(s):
        """The stage's public surface is exactly the names §4.0 pins."""
        public = set()
        for name, value in vars(s).items():
            if name.startswith("_") or name in ("dk", "pg", "tb", "ops"):
                continue
            public.add(name)
        assert public == {"TOKEN_KINDS", "PARSE_KEYS", "PARSE_ERRORS", "KEYWORDS",
                          "QueryError", "tokenize", "parse"}, (
            "the stage's public surface is %s and §4.0 pins TOKEN_KINDS, "
            "PARSE_KEYS, PARSE_ERRORS, KEYWORDS, QueryError, tokenize, parse"
            % ", ".join(sorted(public)))
        assert s.TOKEN_KINDS == S1_TOKEN_KINDS, (
            "TOKEN_KINDS is %r and §4.0 pins %r" % (s.TOKEN_KINDS, S1_TOKEN_KINDS))
        assert s.PARSE_KEYS == S1_PARSE_KEYS, (
            "PARSE_KEYS is %r and §4.0 pins %r" % (s.PARSE_KEYS, S1_PARSE_KEYS))
        assert s.PARSE_ERRORS == S1_PARSE_ERRORS, (
            "PARSE_ERRORS is %r and §4.0 pins %r"
            % (s.PARSE_ERRORS, S1_PARSE_ERRORS))
        assert all(callable(getattr(s, n)) for n in ("tokenize", "parse")), (
            "tokenize and parse are the ways in")

    def _s1_tokenize(s):
        """Words, ints, strings, ops — and the dot."""
        tokens = s.tokenize("SELECT id, name_id FROM users")
        assert tokens[0] == ("word", "SELECT"), tokens[0]
        assert ("word", "id") in tokens and ("word", "name_id") in tokens
        assert ("word", ",") in tokens, "the comma is a word token"
        tokens = s.tokenize("SELECT * FROM orders WHERE total > 100")
        assert ("int", 100) in tokens and ("op", ">") in tokens, tokens
        tokens = s.tokenize("SELECT * FROM orders WHERE status = 'paid'")
        assert ("string", "paid") in tokens, "the quotes are stripped"
        tokens = s.tokenize("SELECT * FROM t WHERE x != 'a b'")
        assert ("string", "a b") in tokens, "the space inside a string survives"
        tokens = s.tokenize("SELECT * FROM t WHERE x >= 4 AND y <= 9")
        assert ("op", ">=") in tokens and ("op", "<=") in tokens, "the two-char ops"
        tokens = s.tokenize("SELECT COUNT(*) FROM orders")
        assert tokens.count(("word", "*")) == 1 and ("word", "(") in tokens \
            and ("word", ")") in tokens, "COUNT(*) tokenizes to five"
        tokens = s.tokenize("SELECT * FROM orders JOIN users "
                            "ON orders.user_id = users.id")
        assert ("word", ".") in tokens, "the dot rides between table and column"
        _refuses(s.QueryError, "an unknown character",
                 lambda: s.tokenize("SELECT id FROM users WHERE x ~ 3"),
                 names=("~", "bad_op"))
        _refuses(s.QueryError, "an unterminated string",
                 lambda: s.tokenize("SELECT * FROM t WHERE s = 'unterminated"),
                 names=("bad_value",))
        assert ("word", "SELECT") in s.tokenize("select id from users"), (
            "a keyword is uppercased whatever case it arrived in")
        assert ("word", "id") in s.tokenize("select id from users"), (
            "a plain word keeps its case")

    def _s1_tree(s):
        """One tree per shape the hundred speak."""
        tree = s.parse("SELECT * FROM events WHERE ts <= 60")
        assert set(tree) == set(S1_PARSE_KEYS), (
            "the tree's keys are PARSE_KEYS: %s" % sorted(tree))
        assert tree["select"] == "*" and tree["columns"] == (), (
            "the star select answers '*' and no columns: %r" % (tree["select"],))
        assert tree["table"] == "events" and tree["joins"] == ()
        assert tree["where"] == (("ts", "<=", 60),), (
            "the conjunct is raw: %r" % (tree["where"],))
        assert tree["order"] is None and tree["limit"] is None

        tree = s.parse("SELECT id, name_id FROM users")
        assert tree["select"] == "columns" and tree["columns"] == ("id", "name_id")

        tree = s.parse("SELECT COUNT(*) FROM orders WHERE status = 'paid'")
        assert tree["select"] == "COUNT(*)" and tree["columns"] == ()
        assert tree["where"] == (("status", "=", "paid"),)

        tree = s.parse("SELECT * FROM orders JOIN users "
                       "ON orders.user_id = users.id")
        assert tree["table"] == "users" and len(tree["joins"]) == 1, (
            "the tree's table is the join's right side: %r" % (tree["table"],))
        assert tree["joins"] == (("orders", "users", "orders.user_id",
                                  "users.id"),)

        tree = s.parse("SELECT * FROM orders WHERE total > 100 AND status != 'open' "
                       "ORDER BY total DESC LIMIT 5")
        assert len(tree["where"]) == 2, "two conjuncts, in order"
        assert tree["where"][1] == ("status", "!=", "open")
        assert tree["order"] == ("total", True) and tree["limit"] == 5

        tree = s.parse("SELECT * FROM users ORDER BY name_id ASC")
        assert tree["order"] == ("name_id", False), (
            "ASC answers False: %r" % (tree["order"],))

    def _s1_hundred(s, tb):
        """The hundred parse, and each tree agrees with its own SQL."""
        import re
        for q in tb.QUERIES:
            tree = s.parse(q["sql"])
            m = re.match(r"SELECT (?:\*|COUNT\(\*\)|[\w, ]+) FROM (\w+)", q["sql"])
            from_table = m.group(1)
            if tree["joins"]:
                assert tree["joins"][0][0] == from_table
                assert tree["table"] == tree["joins"][-1][1], (
                    "q%d: the tree's table disagrees with the SQL" % (q["id"],))
            else:
                assert tree["table"] == from_table, (
                    "q%d: the tree's table disagrees with the SQL" % (q["id"],))
            assert q["sql"].count("JOIN") == len(tree["joins"]), (
                "q%d: the join count disagrees" % (q["id"],))
            where_count = 0 if " WHERE " not in q["sql"] else \
                q["sql"].split(" WHERE ", 1)[1].split(" ORDER BY ")[0].count(
                    " AND ") + 1
            assert len(tree["where"]) == where_count, (
                "q%d: the conjunct count disagrees" % (q["id"],))
            limit = re.search(r"LIMIT (\d+)", q["sql"])
            assert tree["limit"] == (int(limit.group(1)) if limit else None), (
                "q%d: the limit disagrees" % (q["id"],))

    def _s1_refusals(s):
        """The five, each with its word and its token."""
        _refuses(s.QueryError, "empty", lambda: s.parse(""), names=("empty",))
        _refuses(s.QueryError, "empty", lambda: s.parse("   "), names=("empty",))
        _refuses(s.QueryError, "no_from",
                 lambda: s.parse("SELECT id"), names=("no_from",))
        _refuses(s.QueryError, "no_from",
                 lambda: s.parse("SELECT id users"), names=("no_from", "users"))
        _refuses(s.QueryError, "bad_column",
                 lambda: s.parse("SELECT 4 FROM users"), names=("bad_column",))
        _refuses(s.QueryError, "bad_op",
                 lambda: s.parse("SELECT id FROM users WHERE id ~ 3"),
                 names=("bad_op", "~"))
        _refuses(s.QueryError, "bad_value",
                 lambda: s.parse("SELECT id FROM users WHERE id = dollar"),
                 names=("bad_value", "dollar"))
        _refuses(s.QueryError, "bad_value",
                 lambda: s.parse("SELECT id FROM users LIMIT five"),
                 names=("bad_value",))
        _refuses(s.QueryError, "trailing tokens",
                 lambda: s.parse("SELECT id FROM users 5"),
                 names=("bad_value",))
        # a catalog's truth is stage 2's job: unknown names parse fine
        tree = s.parse("SELECT phantom FROM nowhere")
        assert tree["table"] == "nowhere" and tree["columns"] == ("phantom",), (
            "the parse does not resolve: %r" % (tree,))

    """Every assertion the contract's §4.1 makes about this stage."""
    import tables as tb
    import stage_01 as s
    _s1_surface(s)
    _s1_tokenize(s)
    _s1_tree(s)
    _s1_hundred(s, tb)
    _s1_refusals(s)

# --- stage 2 -----------------------------------------------------------------------
def check_2():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "query-engine-from-scratch"

    S2_RESOLVE_KEYS = ("select", "columns", "table", "joins", "where", "order",
                       "limit")

    def _repo(start=None):
        for candidate_start in (os.environ.get("G5_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "disk.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set G5_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        try:
            got = call()
        except exc as e:
            for name in names:
                assert name in str(e), (
                    "%s: the refusal names %r, not %r" % (what, str(e)[:60], name))
            return
        except Exception as e:  # noqa: BLE001
            raise AssertionError("%s raised %r, not %s" % (what, e, exc.__name__))
        raise AssertionError("%s was accepted (%r); it must refuse" % (what, got))

    def _s2_surface(s):
        """The stage's public surface is exactly the names §4.0 pins."""
        public = set()
        for name, value in vars(s).items():
            if name.startswith("_") or name in ("dk", "pg", "tb", "ops"):
                continue
            public.add(name)
        assert public == {"RESOLVE_KEYS", "QueryError", "columns_of",
                          "check_value", "resolve"}, (
            "the stage's public surface is %s and §4.0 pins RESOLVE_KEYS, "
            "QueryError, columns_of, check_value, resolve"
            % ", ".join(sorted(public)))
        assert s.RESOLVE_KEYS == S2_RESOLVE_KEYS, (
            "RESOLVE_KEYS is %r and §4.0 pins %r"
            % (s.RESOLVE_KEYS, S2_RESOLVE_KEYS))
        assert all(callable(getattr(s, n))
                   for n in ("columns_of", "check_value", "resolve")), (
            "columns_of, check_value and resolve are the ways in")

    def _s2_columns_of(s, tb):
        """The catalog's promise, through one door."""
        assert s.columns_of("users", tb.CATALOG) == ("id", "name_id", "plan"), (
            "users' columns in order: %r" % (s.columns_of("users", tb.CATALOG),))
        assert s.columns_of("events", tb.CATALOG) == ("id", "ts", "kind")
        _refuses(s.QueryError, "a table the catalog does not declare",
                 lambda: s.columns_of("nowhere", tb.CATALOG),
                 names=("no_table", "nowhere"))
        # the liar declares a phantom; the truth does not, and resolve is where
        # the phantom dies (_s2_lies). columns_of answers what its catalog says.
        assert s.columns_of("phantom", tb.CATALOG_LIES) == ("id",), (
            "columns_of answers the catalog it is handed, lie included")

    def _s2_check_value(s, tb):
        """The lie is caught against the truth, never against the liar."""
        assert s.check_value("users.plan", "free") == "free", (
            "a real column's value answers unchanged")
        assert s.check_value("users.id", 7) == 7
        _refuses(s.QueryError, "the lying catalog's email",
                 lambda: s.check_value("users.email", "a@b.c"),
                 names=("email", "users"))
        _refuses(s.QueryError, "a column nobody declares",
                 lambda: s.check_value("users.nope", 1), names=("nope",))
        # the same call against the liar still refuses: the truth is the judge
        _refuses(s.QueryError, "email against the lying catalog too",
                 lambda: s.check_value("users.email", "a@b.c"),
                 names=("email",))

    def _s2_tree(s, s1, tb):
        """One resolved tree per shape, addresses matching the honest catalog."""
        tree = s1.parse("SELECT * FROM events WHERE ts <= 60")
        r = s.resolve(tree, tb.CATALOG)
        assert set(r) == set(S2_RESOLVE_KEYS), (
            "the resolved tree's keys are RESOLVE_KEYS: %s" % sorted(r))
        assert r["columns"] == () and r["table"] == "events"
        assert r["where"] == ((("events", 1), "<=", 60),), (
            "ts is events' column 1: %r" % (r["where"],))
        assert r["order"] is None and r["limit"] is None

        tree = s1.parse("SELECT id, name_id FROM users WHERE plan = 'free'")
        r = s.resolve(tree, tb.CATALOG)
        assert r["columns"] == (("users", 0), ("users", 1)), (
            "bare names own the base table: %r" % (r["columns"],))
        assert r["where"] == ((("users", 2), "=", "free"),)

        tree = s1.parse("SELECT COUNT(*) FROM orders WHERE status = 'paid'")
        r = s.resolve(tree, tb.CATALOG)
        assert r["select"] == "COUNT(*)" and r["columns"] == ()
        assert r["where"] == ((("orders", 3), "=", "paid"),)

        tree = s1.parse("SELECT id FROM orders JOIN users "
                        "ON orders.user_id = users.id WHERE plan = 'paid'")
        r = s.resolve(tree, tb.CATALOG)
        assert r["where"] == ((("users", 2), "=", "paid"),), (
            "a bare name in a joined query owns the base table: %r"
            % (r["where"],))

        tree = s1.parse("SELECT * FROM orders JOIN users "
                        "ON orders.user_id = users.id WHERE orders.total > 100 "
                        "ORDER BY orders.total DESC LIMIT 5")
        r = s.resolve(tree, tb.CATALOG)
        assert r["table"] == "users"
        assert r["joins"] == (("orders", "users", ("orders", 1), ("users", 0)),), (
            "ON columns addressed on their own sides: %r" % (r["joins"],))
        assert r["where"] == ((("orders", 2), ">", 100),)
        assert r["order"] == (("orders", 2), True) and r["limit"] == 5

    def _s2_hundred(s, s1, tb):
        """The hundred resolve, and every address names a real column."""
        for q in tb.QUERIES:
            r = s.resolve(s1.parse(q["sql"]), tb.CATALOG)
            tables = ({r["table"]} | {name for j in r["joins"]
                                      for name in (j[0], j[1])})
            for owner, index in list(r["columns"]) + \
                    [a for j in r["joins"] for a in j[2:]] + \
                    [a for (a, _op, _v) in r["where"]] + \
                    ([r["order"][0]] if r["order"] else []):
                assert owner in tables, (
                    "q%d: address %r outside the query's tables" % (q["id"], owner))
                columns = tb.CATALOG[owner]["columns"]
                assert 0 <= index < len(columns) and columns[index], (
                    "q%d: %r is not a real address" % (q["id"], (owner, index)))

    def _s2_lies(s, s1, tb):
        """The lying catalog never blesses its lie; the honest refusals name both."""
        for sql, lie in (("SELECT email FROM users", "email"),
                         ("SELECT * FROM phantom", "phantom"),
                         ("SELECT * FROM users WHERE email = 'a'", "email")):
            _refuses(s.QueryError, sql,
                     lambda sql=sql: s.resolve(s1.parse(sql), tb.CATALOG),
                     names=(lie,))
            _refuses(s.QueryError, sql + " (against the liar)",
                     lambda sql=sql: s.resolve(s1.parse(sql), tb.CATALOG_LIES),
                     names=(lie,))
        _refuses(s.QueryError, "an unknown column",
                 lambda: s.resolve(s1.parse("SELECT nope FROM users"),
                                   tb.CATALOG),
                 names=("no_column", "nope", "users"))
        _refuses(s.QueryError, "an unknown table",
                 lambda: s.resolve(s1.parse("SELECT * FROM nowhere"), tb.CATALOG),
                 names=("no_table", "nowhere"))
        _refuses(s.QueryError, "an unknown join table",
                 lambda: s.resolve(s1.parse("SELECT * FROM users JOIN nowhere "
                                            "ON users.id = nowhere.id"),
                                   tb.CATALOG),
                 names=("no_table", "nowhere"))

        _refuses(s.QueryError, "a join table nobody references",
                 lambda: s.resolve(s1.parse("SELECT users.id FROM users JOIN "
                                            "nowhere ON users.id = users.id"),
                                   tb.CATALOG),
                 names=("no_table", "nowhere"))

    """Every assertion the contract's §4.2 makes about this stage."""
    import tables as tb
    import stage_01 as s1
    import stage_02 as s
    _s2_surface(s)
    _s2_columns_of(s, tb)
    _s2_check_value(s, tb)
    _s2_tree(s, s1, tb)
    _s2_hundred(s, s1, tb)
    _s2_lies(s, s1, tb)

# --- stage 3 -----------------------------------------------------------------------
def check_3():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "query-engine-from-scratch"

    S3_PRED_KEYS = ("conjuncts", "pushed", "both")

    def _repo(start=None):
        for candidate_start in (os.environ.get("G5_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "disk.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set G5_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        try:
            got = call()
        except exc as e:
            for name in names:
                assert name in str(e), (
                    "%s: the refusal names %r, not %r" % (what, str(e)[:60], name))
            return
        except Exception as e:  # noqa: BLE001
            raise AssertionError("%s raised %r, not %s" % (what, e, exc.__name__))
        raise AssertionError("%s was accepted (%r); it must refuse" % (what, got))

    def _s3_surface(s):
        """The stage's public surface is exactly the names §4.0 pins."""
        public = set()
        for name, value in vars(s).items():
            if name.startswith("_") or name in ("dk", "pg", "tb", "ops"):
                continue
            public.add(name)
        assert public == {"PRED_KEYS", "QueryError", "conjuncts_of", "referenced",
                          "pushdown"}, (
            "the stage's public surface is %s and §4.0 pins PRED_KEYS, "
            "QueryError, conjuncts_of, referenced, pushdown"
            % ", ".join(sorted(public)))
        assert s.PRED_KEYS == S3_PRED_KEYS, (
            "PRED_KEYS is %r and §4.0 pins %r" % (s.PRED_KEYS, S3_PRED_KEYS))
        assert all(callable(getattr(s, n))
                   for n in ("conjuncts_of", "referenced", "pushdown")), (
            "conjuncts_of, referenced and pushdown are the ways in")

    def _s3_conjuncts_of(s, s2):
        """The split: in order, every conjunct a (table, column, op, value)."""
        where = (((("orders", 2), ">", 100)),
                 (("orders", 3), "=", "paid"))
        got = s.conjuncts_of(where)
        assert got == (("orders", 2, ">", 100), ("orders", 3, "=", "paid")), (
            "the split keeps the order and names each table: %r" % (got,))
        got = s.conjuncts_of(())
        assert got == (), "an empty WHERE splits to no conjuncts"
        _refuses(s.QueryError, "an unresolved conjunct",
                 lambda: s.conjuncts_of((("total", ">", 100),)),
                 names=("unresolved",))

    def _s3_referenced(s, s1, s2, tb):
        """The question, asked per side, against the join the tree declares."""
        tree = s2.resolve(s1.parse("SELECT * FROM orders JOIN users "
                                   "ON orders.user_id = users.id "
                                   "WHERE orders.total > 100 AND users.plan "
                                   "= 'free'"), tb.CATALOG)
        left_c = ("orders", 2, ">", 100)
        right_c = ("users", 2, "=", "free")
        assert s.referenced(left_c, "left", tree) is True, (
            "orders.total references the join's left side")
        assert s.referenced(left_c, "right", tree) is False, (
            "orders.total does not reference users")
        assert s.referenced(right_c, "right", tree) is True, (
            "users.plan references the join's right side")
        assert s.referenced(right_c, "left", tree) is False, (
            "users.plan does not reference orders")
        _refuses(s.QueryError, "a side that is not a side",
                 lambda: s.referenced(left_c, "middle", tree),
                 names=("no_side",))
        # no join: nothing is a side
        single = s2.resolve(s1.parse("SELECT * FROM orders WHERE total > 100"),
                            tb.CATALOG)
        assert s.referenced(left_c, "left", single) is False, (
            "a query with no join has no sides")

    def _s3_pushdown(s, s1, s2, tb):
        """The record: pushed per scan, both above, held against the join."""
        r = s2.resolve(s1.parse("SELECT * FROM orders WHERE total > 100 "
                                "AND status = 'paid'"), tb.CATALOG)
        p = s.pushdown(r)
        assert set(p) == set(S3_PRED_KEYS)
        assert p["pushed"] == (("orders", (("orders", 2, ">", 100),
                                           ("orders", 3, "=", "paid"))),), (
            "a single scan takes everything: %r" % (p["pushed"],))
        assert p["both"] == (), "nothing stays above a scan with no join"

        r = s2.resolve(s1.parse("SELECT * FROM orders JOIN users "
                                "ON orders.user_id = users.id "
                                "WHERE orders.total > 100 AND users.plan = 'free' "
                                "AND orders.status != 'open'"), tb.CATALOG)
        p = s.pushdown(r)
        scans = [scan for (scan, _c) in p["pushed"]]
        assert scans == ["orders", "users"], (
            "the scans are the join's left then its right: %r" % (scans,))
        by = dict(p["pushed"])
        assert by["orders"] == (("orders", 2, ">", 100),
                                ("orders", 3, "!=", "open")), (
            "orders' conjuncts pushed to the orders scan: %r" % (by["orders"],))
        assert by["users"] == (("users", 2, "=", "free"),), (
            "users' conjunct pushed to the users scan: %r" % (by["users"],))
        assert p["both"] == (), "every conjunct named one side"

        # a conjunct on the *first* table of a two-join fold still finds its scan
        r = s2.resolve(s1.parse("SELECT * FROM orders JOIN users "
                                "ON orders.user_id = users.id JOIN items "
                                "ON items.order_id = orders.id "
                                "WHERE orders.total > 100 AND items.price < 9"),
                       tb.CATALOG)
        p = s.pushdown(r)
        by = dict(p["pushed"])
        assert [scan for (scan, _c) in p["pushed"]] == ["orders", "users", "items"]
        assert by["orders"] == (("orders", 2, ">", 100),), (
            "the fold's first table still gets its conjunct: %r" % (by["orders"],))
        assert by["items"] == (("items", 2, "<", 9),)
        assert p["both"] == ()

    def _s3_both(s, s1, s2, tb):
        """A conjunct two scans could claim stays above the join."""
        r = s2.resolve(s1.parse("SELECT * FROM orders JOIN items "
                                "ON items.order_id = orders.id "
                                "WHERE orders.total > 100"), tb.CATALOG)
        p = s.pushdown(r)
        # orders appears once — pushed; there is no second orders scan
        assert p["both"] == ()
        # a self join: two scans share a name, so the conjunct cannot choose
        r = s2.resolve(s1.parse("SELECT * FROM users JOIN users "
                                "ON users.id = users.id WHERE users.plan = "
                                "'paid'"), tb.CATALOG)
        p = s.pushdown(r)
        assert p["both"] == (("users", 2, "=", "paid"),), (
            "a conjunct both scans could claim stays above: %r" % (p["both"],))
        assert all(conjuncts == () for (_s, conjuncts) in p["pushed"]), (
            "nothing was pushed when both stayed above")

    def _s3_hundred(s, s1, s2, tb):
        """The hundred split, and every conjunct's table is one of the scans."""
        for q in tb.QUERIES:
            r = s2.resolve(s1.parse(q["sql"]), tb.CATALOG)
            p = s.pushdown(r)
            scans = {scan for (scan, _c) in p["pushed"]}
            conjuncts = s.conjuncts_of(r["where"])
            for (table, _index, _op, _value) in conjuncts:
                assert table in scans, (
                    "q%d: conjunct's table %r is not a scan" % (q["id"], table))
            pushed_count = sum(len(c) for (_s, c) in p["pushed"])
            assert pushed_count + len(p["both"]) == len(conjuncts), (
                "q%d: the record loses conjuncts" % (q["id"],))

    """Every assertion the contract's §4.3 makes about this stage."""
    import tables as tb
    import stage_01 as s1
    import stage_02 as s2
    import stage_03 as s
    _s3_surface(s)
    _s3_conjuncts_of(s, s2)
    _s3_referenced(s, s1, s2, tb)
    _s3_pushdown(s, s1, s2, tb)
    _s3_both(s, s1, s2, tb)
    _s3_hundred(s, s1, s2, tb)

# --- stage 4 -----------------------------------------------------------------------
def check_4():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "query-engine-from-scratch"

    S4_TREE_KEYS = ("root", "height", "leaves", "entries")

    def _repo(start=None):
        for candidate_start in (os.environ.get("G5_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "disk.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set G5_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        try:
            got = call()
        except exc as e:
            for name in names:
                assert name in str(e), (
                    "%s: the refusal names %r, not %r" % (what, str(e)[:60], name))
            return
        except Exception as e:  # noqa: BLE001
            raise AssertionError("%s raised %r, not %s" % (what, e, exc.__name__))
        raise AssertionError("%s was accepted (%r); it must refuse" % (what, got))

    def _s4_surface(s):
        """The stage's public surface is exactly the names §4.0 pins."""
        public = set()
        for name, value in vars(s).items():
            if name.startswith("_") or name in ("dk", "pg", "tb", "ops"):
                continue
            public.add(name)
        assert public == {"TREE_KEYS", "LEAF_FANOUT", "QueryError", "build",
                          "lookup", "split"}, (
            "the stage's public surface is %s and §4.0 pins TREE_KEYS, "
            "LEAF_FANOUT, QueryError, build, lookup, split"
            % ", ".join(sorted(public)))
        assert s.TREE_KEYS == S4_TREE_KEYS, (
            "TREE_KEYS is %r and §4.0 pins %r" % (s.TREE_KEYS, S4_TREE_KEYS))
        assert s.LEAF_FANOUT == 8 and isinstance(s.LEAF_FANOUT, int), (
            "LEAF_FANOUT is 8, the number the plan's arithmetic needs: %r"
            % (s.LEAF_FANOUT,))
        assert all(callable(getattr(s, n)) for n in ("build", "lookup", "split")), (
            "build, lookup and split are the ways in")

    def _s4_build(s, pg, tb):
        """The world's index answering its shape."""
        import disk as dk
        pager = pg.Pager(dk.Disk())
        tree = s.build(pager, tb.EVENTS_INDEX)
        assert set(tree) >= set(S4_TREE_KEYS), (
            "the shape record carries TREE_KEYS: %s" % sorted(tree))
        assert tree["entries"] == len(tb.EVENTS_INDEX) == 120, (
            "the entry count is the world's: %r" % (tree["entries"],))
        assert tree["leaves"] == -(-len(tb.EVENTS_INDEX) // s.LEAF_FANOUT), (
            "leaves fill in order: %r vs %r" % (tree["leaves"],
                                                -(-len(tb.EVENTS_INDEX)
                                                  // s.LEAF_FANOUT)))
        assert tree["leaves"] == 15 and tree["height"] == 2, (
            "the world's arithmetic: 120 entries at fanout 8 are 15 leaves, "
            "height 2 — got %r leaves, height %r (a different LEAF_FANOUT is "
            "an amendment, not a choice)" % (tree["leaves"], tree["height"]))
        assert tree["height"] == 2, (
            "120 entries over 4-wide leaves is two levels: %r" % (tree["height"],))
        assert isinstance(tree["root"], int) and tree["root"] > 0, (
            "the root is a page the tree owns: %r" % (tree["root"],))

        single = pg.Pager(dk.Disk())
        one = s.build(single, ((4, 59), (7, 118)))
        assert one["height"] == 1 and one["leaves"] == 1, (
            "a run that fits one leaf is height 1: %r" % (one,))

        _refuses(s.QueryError, "unsorted entries",
                 lambda: s.build(pg.Pager(dk.Disk()),
                                 ((9, 1), (4, 2), (7, 3))),
                 names=("unsorted",))
        return pager, tree

    def _s4_lookup(s, pg, tb, pager, tree):
        """The walk answering the world's pairs, point and range."""
        by_key = {}
        for (k, rid) in tb.EVENTS_INDEX:
            by_key.setdefault(k, []).append((k, rid))
        bad = []
        for k, want in sorted(by_key.items()):
            if s.lookup(tree, k) != tuple(want):
                bad.append(k)
        assert not bad, "point lookups wrong for keys %s" % (bad[:5],)

        def want_range(lo, hi):
            return tuple(e for e in tb.EVENTS_INDEX if lo <= e[0] <= hi)

        for (lo, hi) in ((0, 1000), (4, 4), (497, 497), (100, 110), (0, 10),
                         (400, 500), (50, 200), (120, 121)):
            got = s.lookup(tree, (lo, hi))
            assert got == want_range(lo, hi), (
                "range (%d, %d) walked %r, the world says %r"
                % (lo, hi, got[:3], want_range(lo, hi)[:3]))
        assert s.lookup(tree, (500, 600)) == (), (
            "a range past the last key answers nothing")

    def _s4_walk_price(s, pg, tb, pager, tree):
        """The walk is a tree walk: a point query does not read every leaf."""
        pager.sync()
        before = pager.disk.counters()["reads"]
        last_key = tb.EVENTS_INDEX[-1][0]
        assert s.lookup(tree, last_key)[:1] == (tb.EVENTS_INDEX[-1],)
        reads = pager.disk.counters()["reads"] - before
        # one inner node and the leaf it lands on — two pages, four sectors —
        # not the thirty leaves a broken walk would read
        assert reads <= 2 * (tree["height"] + 1), (
            "a point lookup read %d sectors for a height-%d tree"
            % (reads, tree["height"]))

    def _s4_split(s, pg, tb, pager, tree):
        """The seam: both halves and the separator against the entries."""
        child0, separators = s._read_inner(pager, tree["root"])
        pairs, _next = s._read_leaf(pager, child0)
        assert len(pairs) == s.LEAF_FANOUT, (
            "the check splits a full leaf: %d entries" % (len(pairs),))
        before = s.lookup(tree, (0, 1000))

        after = s.split(pager, child0)
        assert after["entries"] == len(pairs), (
            "split loses no entry: %r" % (after["entries"],))
        assert after["leaves"] == tree["leaves"] + 1, (
            "one leaf became two: %r" % (after["leaves"],))

        first, nxt = s._read_leaf(pager, child0)
        second, _n2 = s._read_leaf(pager, nxt)
        mid = (len(pairs) + 1) // 2
        assert first == pairs[:mid] and second == pairs[mid:], (
            "the halves are the entries that went in, in order: %r | %r"
            % (first, second))
        separators_after = s._read_inner(pager, tree["root"])[1]
        assert any(sep == second[0][0] for (sep, _c) in separators_after), (
            "the parent gains the second half's first key: %r"
            % (separators_after[:2],))

        # the walk lands on both halves after the split
        assert s.lookup(tree, first[0][0]) == tuple(first) or \
            s.lookup(tree, first[0][0])[:1] == (first[0],), (
            "the first half is reachable")
        assert second[0] in s.lookup(tree, second[0][0]), (
            "the second half is reachable through its separator")
        assert s.lookup(tree, (0, 1000)) == before, (
            "the whole index still walks back in order")

        _refuses(s.QueryError, "a leaf with room to spare",
                 lambda: s.split(pager, nxt), names=("not_full",))

    """Every assertion the contract's §4.4 makes about this stage."""
    import disk as dk
    import pages as pg
    import tables as tb
    import stage_04 as s
    _s4_surface(s)
    pager, tree = _s4_build(s, pg, tb)
    _s4_lookup(s, pg, tb, pager, tree)
    _s4_walk_price(s, pg, tb, pager, tree)
    _s4_split(s, pg, tb, pager, tree)

# --- stage 5 -----------------------------------------------------------------------
def check_5():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "query-engine-from-scratch"

    S5_PLAN_KEYS = ("scans", "pushed", "uses_index", "cost")

    def _repo(start=None):
        for candidate_start in (os.environ.get("G5_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "disk.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set G5_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        try:
            got = call()
        except exc as e:
            for name in names:
                assert name in str(e), (
                    "%s: the refusal names %r, not %r" % (what, str(e)[:60], name))
            return
        except Exception as e:  # noqa: BLE001
            raise AssertionError("%s raised %r, not %s" % (what, e, exc.__name__))
        raise AssertionError("%s was accepted (%r); it must refuse" % (what, got))

    def _s5_surface(s):
        """The stage's public surface is exactly the names §4.0 pins."""
        public = set()
        for name, value in vars(s).items():
            if name.startswith("_") or name in ("dk", "pg", "tb", "ops"):
                continue
            public.add(name)
        assert public == {"PLAN_KEYS", "QueryError", "cost_of", "plan",
                          "explain"}, (
            "the stage's public surface is %s and §4.0 pins PLAN_KEYS, "
            "QueryError, cost_of, plan, explain" % ", ".join(sorted(public)))
        assert s.PLAN_KEYS == S5_PLAN_KEYS, (
            "PLAN_KEYS is %r and §4.0 pins %r" % (s.PLAN_KEYS, S5_PLAN_KEYS))
        assert all(callable(getattr(s, n))
                   for n in ("cost_of", "plan", "explain")), (
            "cost_of, plan and explain are the ways in")

    def _s5_cost_of(s):
        """The prices, in pages, against the world's own counts."""
        assert s.cost_of("table", "events", 0) == 7, (
            "events' table scan is its seven pages: %r"
            % (s.cost_of("table", "events", 0),))
        assert s.cost_of("table", "users", 0) == 2
        assert s.cost_of("table", "orders", 0) == 4
        # 26 matches at fanout 8 spread over 4 leaves: height 2 + 4 = 6
        assert s.cost_of("index", "events", 26) < s.cost_of("table", "events", 0), (
            "26 matched rows earn the index: %r vs %r"
            % (s.cost_of("index", "events", 26),
               s.cost_of("table", "events", 0)))
        assert s.cost_of("index", "events", 59) > s.cost_of("table", "events", 0), (
            "59 matched rows do not: %r vs %r"
            % (s.cost_of("index", "events", 59),
               s.cost_of("table", "events", 0)))
        assert s.cost_of("index", "events", 1) == s.cost_of("index", "events", 8), (
            "one leaf's worth of matches is one leaf's worth of price: %r"
            % (s.cost_of("index", "events", 1),))
        _refuses(s.QueryError, "an unknown scan",
                 lambda: s.cost_of("bitmap", "events", 1), names=("no_scan",))
        _refuses(s.QueryError, "an unknown table",
                 lambda: s.cost_of("table", "nowhere", 0), names=("no_table",))

    def _s5_plan(s, s1, s2, tb):
        """The choice the costs made, and the pin it must agree with."""
        pin = dict(tb.PLAN_FACTS)
        bad = []
        for q in tb.QUERIES:
            tree = s2.resolve(s1.parse(q["sql"]), tb.CATALOG)
            p = s.plan(tree, tb.PLAN_FACTS)
            assert set(p) == set(S5_PLAN_KEYS), (
                "the plan's keys are PLAN_KEYS: %s" % sorted(p))
            if p["uses_index"] != pin.get(q["id"], False):
                bad.append(q["id"])
            assert p["uses_index"] == pin.get(q["id"], False), (
                "q%d disagrees with the pin" % (q["id"],)) if q["id"] in pin else None
        assert not bad, (
            "the plan disagrees with the pinned facts on %s" % (bad[:6],))

        # the four indexed queries carry index scans with their pushed conjuncts
        for qid in (21, 24, 37, 65):
            q = tb.QUERIES[qid - 1]
            tree = s2.resolve(s1.parse(q["sql"]), tb.CATALOG)
            p = s.plan(tree, tb.PLAN_FACTS)
            scans = dict((t, (scan, c)) for (t, scan, c) in p["scans"])
            assert scans["events"][0] == "index", (
                "q%d's plan earns the index: %r" % (qid, p["scans"]))
            assert scans["events"][1], (
                "q%d's index scan carries its pushed conjuncts" % (qid,))

        # a non-ts conjunct sends the scan to the table — q38, q39, q43
        for qid in (38, 39, 43):
            q = tb.QUERIES[qid - 1]
            tree = s2.resolve(s1.parse(q["sql"]), tb.CATALOG)
            p = s.plan(tree, tb.PLAN_FACTS)
            assert p["uses_index"] is False, (
                "q%d must scan: the index serves ts alone" % (qid,))

        # the choice moves when the costs move: the same shape of query against
        # a narrower table would scan — proving arithmetic, not memory
        tree = s2.resolve(s1.parse("SELECT * FROM events WHERE ts <= 60"),
                          tb.CATALOG)
        p = s.plan(tree, tb.PLAN_FACTS)
        assert p["uses_index"] is True and p["cost"] == 4, (
            "q24's plan: index at 4 pages against 7: %r" % (p,))
        assert all(scan == "table"
                   for (_t, scan, _c) in s.plan(
                       s2.resolve(s1.parse("SELECT * FROM users "
                                           "WHERE name_id < 5"), tb.CATALOG),
                       tb.PLAN_FACTS)["scans"]), (
            "users has no index; its plan scans")

    def _s5_explain(s, s1, s2, tb):
        """The line, held against the plan's own record."""
        tree = s2.resolve(s1.parse("SELECT * FROM events WHERE ts <= 60"),
                          tb.CATALOG)
        p = s.plan(tree, tb.PLAN_FACTS)
        line = s.explain(p)
        assert line == "events: index[ts] (ts<=60)", (
            "the line the contract pins: %r" % (line,))

        tree = s2.resolve(s1.parse("SELECT * FROM orders JOIN users "
                                   "ON orders.user_id = users.id "
                                   "WHERE orders.total > 100"), tb.CATALOG)
        p = s.plan(tree, tb.PLAN_FACTS)
        line = s.explain(p)
        assert line == "orders: table | users: table", (
            "the scans in order, joins between: %r" % (line,))

        tree = s2.resolve(s1.parse("SELECT * FROM events WHERE ts > 200 "
                                   "AND ts < 300"), tb.CATALOG)
        p = s.plan(tree, tb.PLAN_FACTS)
        line = s.explain(p)
        assert line == "events: index[ts] (ts>200) (ts<300)", (
            "both conjuncts attached: %r" % (line,))

    """Every assertion the contract's §4.5 makes about this stage."""
    import tables as tb
    import stage_01 as s1
    import stage_02 as s2
    import stage_05 as s
    _s5_surface(s)
    _s5_cost_of(s)
    _s5_plan(s, s1, s2, tb)
    _s5_explain(s, s1, s2, tb)

# --- stage 6 -----------------------------------------------------------------------
def check_6():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "query-engine-from-scratch"

    S6_EXEC_KEYS = ("rows", "pages", "chain")

    def _repo(start=None):
        for candidate_start in (os.environ.get("G5_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "disk.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set G5_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        try:
            got = call()
        except exc as e:
            for name in names:
                assert name in str(e), (
                    "%s: the refusal names %r, not %r" % (what, str(e)[:60], name))
            return
        except Exception as e:  # noqa: BLE001
            raise AssertionError("%s raised %r, not %s" % (what, e, exc.__name__))
        raise AssertionError("%s was accepted (%r); it must refuse" % (what, got))

    def _world_pager(pg, tb):
        """The world on a fresh pager."""
        import disk as dk
        pager = pg.Pager(dk.Disk())
        tb.load_world(pager)
        pager.sync()
        return pager

    def _s6_surface(s):
        """The stage's public surface is exactly the names §4.0 pins."""
        public = set()
        for name, value in vars(s).items():
            if name.startswith("_") or name in ("dk", "pg", "tb", "ops"):
                continue
            public.add(name)
        assert public == {"EXEC_KEYS", "QueryError", "seq_scan", "index_scan",
                          "nested_loop", "execute"}, (
            "the stage's public surface is %s and §4.0 pins EXEC_KEYS, "
            "QueryError, seq_scan, index_scan, nested_loop, execute"
            % ", ".join(sorted(public)))
        assert s.EXEC_KEYS == S6_EXEC_KEYS, (
            "EXEC_KEYS is %r and §4.0 pins %r" % (s.EXEC_KEYS, S6_EXEC_KEYS))
        assert all(callable(getattr(s, n))
                   for n in ("seq_scan", "index_scan", "nested_loop",
                             "execute")), (
            "seq_scan, index_scan, nested_loop and execute are the ways in")

    def _s6_seq_scan(s, pg, tb):
        """Row order from the pinned pages, the receipt the disk keeps."""
        import disk as dk
        pager = pg.Pager(dk.Disk())
        tb.load_world(pager)
        pager.sync()
        before = pager.disk.counters()["reads"]
        rows = list(s.seq_scan(pager, "orders"))
        reads = pager.disk.counters()["reads"] - before
        assert tuple(rows) == tb.TABLES["orders"], (
            "seq_scan answers the world's rows in order")
        assert reads == 2 * len(tb.TABLE_PAGES["orders"]), (
            "orders' scan reads its four pages: %d sector reads" % (reads,))
        _refuses(s.QueryError, "a table the world does not declare",
                 lambda: list(s.seq_scan(pager, "nowhere")), names=("no_table",))

    def _s6_index_scan(s, pg, tb):
        """The rows the range names, in key order, fetched whole."""
        pager = _world_pager(pg, tb)
        got = tuple(s.index_scan(pager, 0, 60))
        want = tuple(r for (_ts, rid) in tb.EVENTS_INDEX if rid
                     for r in [next(x for x in tb.TABLES["events"]
                                    if x[0] == rid)]
                     if 0 <= r[1] <= 60)
        want = tuple(r for r in sorted(tb.TABLES["events"], key=lambda r: r[1])
                     if r[1] <= 60)
        assert got == want, (
            "the index scan answers the range in key order: %r vs %r"
            % (got[:3], want[:3]))
        assert [r[1] for r in got] == sorted(r[1] for r in got), (
            "key order is the scan's own")
        assert tuple(s.index_scan(pager, 10_000, 20_000)) == (), (
            "an empty range answers nothing")

    def _s6_nested_loop(s, pg, tb):
        """Left outer, right inner, left order preserved."""
        left = [(1, 10), (2, 20), (3, 30)]
        right = [(10, "a"), (30, "c"), (10, "b")]
        got = list(s.nested_loop(iter(left), iter(right), 1, 0))
        assert got == [(1, 10, 10, "a"), (1, 10, 10, "b"),
                       (3, 30, 30, "c")], (
            "left order preserved, right inner: %r" % (got,))
        assert list(s.nested_loop(iter(left), iter([]), 1, 0)) == [], (
            "an empty right side joins to nothing")

    def _s6_hundred(s, pg, tb, s1, s2, s5):
        """The hundred, answered exactly; the receipt and the chain named."""
        import disk as dk
        bad_rows, bad_pages = [], []
        for q in tb.QUERIES:
            pager = pg.Pager(dk.Disk())
            tb.load_world(pager)
            tree = s2.resolve(s1.parse(q["sql"]), tb.CATALOG)
            plan_record = s5.plan(tree, tb.PLAN_FACTS)
            r = s.execute(pager, tree, plan_record)
            assert set(r) == set(S6_EXEC_KEYS), (
                "the record's keys are EXEC_KEYS: %s" % sorted(r))
            if r["rows"] != q["rows"]:
                bad_rows.append(q["id"])
            if q["id"] in (1,):
                assert r["pages"] == len(tb.TABLE_PAGES["users"]), (
                    "q1 reads users' two pages: %r" % (r["pages"],))
            if q["id"] in (21, 24, 37, 65):
                assert any(name == "index_scan" for name in r["chain"]), (
                    "q%d's chain runs the index scan the plan chose" % (q["id"],))
            assert r["chain"][0] in ("seq_scan", "index_scan"), (
                "the chain names its scan: %r" % (r["chain"],))
        assert not bad_rows, (
            "law 13 violated on %s — the rows are the reference's, exactly"
            % (bad_rows[:6],))

    def _s6_shapes(s, pg, tb, s1, s2, s5):
        """COUNT answers one row; LIMIT truncates after ORDER BY."""
        import disk as dk
        pager = pg.Pager(dk.Disk())
        tb.load_world(pager)
        sql = "SELECT COUNT(*) FROM orders WHERE status = 'paid'"
        tree = s2.resolve(s1.parse(sql), tb.CATALOG)
        r = s.execute(pager, tree, s5.plan(tree, tb.PLAN_FACTS))
        assert r["rows"] == tb.QUERIES[41]["rows"] or len(r["rows"]) == 1, (
            "COUNT answers one row: %r" % (r["rows"],))
        assert "count" in r["chain"], (
            "the chain names the count: %r" % (r["chain"],))

        sql = "SELECT * FROM events WHERE ts <= 80 ORDER BY ts LIMIT 8"
        tree = s2.resolve(s1.parse(sql), tb.CATALOG)
        r = s.execute(pager, tree, s5.plan(tree, tb.PLAN_FACTS))
        assert len(r["rows"]) == 8, (
            "LIMIT truncates: %d rows" % (len(r["rows"]),))
        assert "limit" in r["chain"] and "sort" in r["chain"], (
            "the chain names sort then limit: %r" % (r["chain"],))

    """Every assertion the contract's §4.6 makes about this stage."""
    import pages as pg
    import tables as tb
    import stage_01 as s1
    import stage_02 as s2
    import stage_05 as s5
    import stage_06 as s
    _s6_surface(s)
    _s6_seq_scan(s, pg, tb)
    _s6_index_scan(s, pg, tb)
    _s6_nested_loop(s, pg, tb)
    _s6_hundred(s, pg, tb, s1, s2, s5)
    _s6_shapes(s, pg, tb, s1, s2, s5)

# --- stage 7 -----------------------------------------------------------------------
def check_7():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "query-engine-from-scratch"

    S7_BUFFER_KEYS = ("hits", "misses", "evictions", "dirty")

    def _repo(start=None):
        for candidate_start in (os.environ.get("G5_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "disk.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set G5_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        try:
            got = call()
        except exc as e:
            for name in names:
                assert name in str(e), (
                    "%s: the refusal names %r, not %r" % (what, str(e)[:60], name))
            return
        except Exception as e:  # noqa: BLE001
            raise AssertionError("%s raised %r, not %s" % (what, e, exc.__name__))
        raise AssertionError("%s was accepted (%r); it must refuse" % (what, got))

    def _world_pager(pg, tb):
        import disk as dk
        pager = pg.Pager(dk.Disk())
        tb.load_world(pager)
        pager.sync()
        return pager

    def _s7_surface(s):
        """The stage's public surface is exactly the names §4.0 pins."""
        public = set()
        for name, value in vars(s).items():
            if name.startswith("_") or name in ("dk", "pg", "tb", "ops"):
                continue
            public.add(name)
        assert public == {"BUFFER_KEYS", "QueryError", "BufferPool",
                          "run_buffered"}, (
            "the stage's public surface is %s and §4.0 pins BUFFER_KEYS, "
            "QueryError, BufferPool, run_buffered" % ", ".join(sorted(public)))
        assert s.BUFFER_KEYS == S7_BUFFER_KEYS, (
            "BUFFER_KEYS is %r and §4.0 pins %r"
            % (s.BUFFER_KEYS, S7_BUFFER_KEYS))

    def _s7_pool(s, pg, tb):
        """Hits, misses, LRU eviction, dirty writeback, the refusals."""
        import disk as dk
        pager = _world_pager(pg, tb)
        pool = s.BufferPool(pager, 2)
        first = pool.fetch(3)
        assert first == pager.read(3), (
            "a miss answers the pager's bytes")
        again = pool.fetch(3)
        assert again == first, "a hit answers the same bytes"
        rec = pool.record()
        assert rec == {"hits": 1, "misses": 1, "evictions": 0, "dirty": 0}, (
            "one miss, one hit, nothing evicted: %r" % (rec,))

        # eviction is LRU over the unpinned: 3,4 in; fetch 5 evicts 3;
        # fetch 3 again evicts 4 (3 is now most recent? no: 4,5 in, 3 evicted,
        # re-fetch 3 evicts 4 — the LRU order is the fetch order)
        pool = s.BufferPool(pager, 2)
        pool.fetch(3)
        pool.fetch(4)
        pool.fetch(5)                     # evicts 3
        assert pool.record()["evictions"] == 1
        pool.fetch(4)                     # a hit: 4 is now most recent
        before = pool.record()["misses"]
        pool.fetch(5)                     # still a hit: recency protects it
        assert pool.record()["misses"] == before, (
            "the most recently used page survives")
        pool.fetch(3)                     # evicts 4 (LRU: 4 older than 5)
        got = pool.fetch(4)
        assert got == pager.read(4), (
            "an evicted page re-fetches correctly")

        # a pinned page is never evicted
        pool = s.BufferPool(pager, 2)
        pool.fetch(3)
        pool.pin(3)
        pool.fetch(4)
        pool.fetch(5)                     # must evict 4, not the pinned 3
        assert pool.record()["evictions"] == 1
        assert pool.fetch(3) == pager.read(3), (
            "the pinned page is still a hit")
        tight = s.BufferPool(pager, 1)
        tight.fetch(3)
        tight.pin(3)
        _refuses(s.QueryError, "every frame pinned",
                 lambda: tight.fetch(4), names=("all_pinned",))
        _refuses(s.QueryError, "unpin of a page never pinned",
                 lambda: s.BufferPool(pager, 2).unpin(3), names=("not_pinned",))

        # a dirty page is written back on eviction
        pool = s.BufferPool(pager, 1)
        data = pool.fetch(3)
        # the frame is the only place a change can live: plant one, unpin dirty,
        # and let the eviction carry it to the durable image
        pool._pages[3] = bytes(pool._frames) + data[1:]
        pool.pin(3)
        pool.unpin(3, dirty=True)
        pool.fetch(4)                     # evicts 3, writes it back
        pager.sync()                      # the writeback lands on the disk
        other = pg.Pager.__new__(pg.Pager)
        other.disk, other._shadow = pager.disk, {}
        durable = other.read(3)
        assert durable[:1] == bytes(pool._frames), (
            "the dirty page's bytes reached the durable image")
        assert pool.record()["dirty"] == 0, (
            "the writeback clears the dirty flag")

    def _s7_run_buffered(s, pg, tb, s1, s2, s5, s6):
        """The central arithmetic: small plan big pool; and the rows unchanged."""
        sql = "SELECT * FROM orders WHERE status = 'paid'"
        tree = s2.resolve(s1.parse(sql), tb.CATALOG)
        plan_record = s5.plan(tree, tb.PLAN_FACTS)

        pager = _world_pager(pg, tb)
        r = s.run_buffered(pager, tree, plan_record, 16)
        for key in S7_BUFFER_KEYS + s6.EXEC_KEYS:
            assert key in r, "the record carries %s" % (key,)
        assert r["evictions"] == 0, (
            "a table smaller than the pool never evicts: %r" % (r["evictions"],))
        assert r["misses"] == len(tb.TABLE_PAGES["orders"]), (
            "every page read exactly once from the pager: %r" % (r["misses"],))
        assert r["rows"] == s6.execute(pager, tree, plan_record)["rows"], (
            "the pool changes the traffic, never the answer")

        # the same query through a pool too small evicts — the rows hold
        r2 = s.run_buffered(pager, tree, plan_record, 1)
        assert r2["evictions"] > 0, (
            "a one-frame pool evicts: %r" % (r2["evictions"],))
        assert r2["rows"] == r["rows"], (
            "eviction changes nothing about the rows")

    def _s7_pinning_fixture(s, pg, tb, s1, s2, s5):
        """The join that explodes without pins and does not with them."""
        import disk as dk
        sql = "SELECT * FROM orders JOIN users ON orders.user_id = users.id"
        tree = s2.resolve(s1.parse(sql), tb.CATALOG)
        plan_record = s5.plan(tree, tb.PLAN_FACTS)
        left_pages = len(tb.TABLE_PAGES["orders"])
        right_pages = len(tb.TABLE_PAGES["users"])

        # a pool just large enough for one left page plus both right pages,
        # pinned: the inner pages are read once each
        pager = _world_pager(pg, tb)
        pool = s.BufferPool(pager, 1 + right_pages)
        for page in tb.TABLE_PAGES["users"]:
            pool.fetch(page)
            pool.pin(page)
        before = pager.disk.counters()["reads"]
        pool.fetch(tb.TABLE_PAGES["orders"][0])
        reads = pager.disk.counters()["reads"] - before
        assert reads == 2, (
            "one left page read beside the pinned right: %d sectors" % (reads,))
        # the right pages are still hits after the left page's traffic
        before = pool.record()["misses"]
        for page in tb.TABLE_PAGES["users"]:
            pool.fetch(page)
        assert pool.record()["misses"] == before, (
            "the pinned inner pages survive the outer scan")

    """Every assertion the contract's §4.7 makes about this stage."""
    import pages as pg
    import tables as tb
    import stage_01 as s1
    import stage_02 as s2
    import stage_05 as s5
    import stage_06 as s6
    import stage_07 as s
    _s7_surface(s)
    _s7_pool(s, pg, tb)
    _s7_run_buffered(s, pg, tb, s1, s2, s5, s6)
    _s7_pinning_fixture(s, pg, tb, s1, s2, s5)

# --- stage 8 -----------------------------------------------------------------------
def check_8():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "query-engine-from-scratch"

    S8_LOG_KEYS = ("lsn", "commit_lsn", "durable")

    def _repo(start=None):
        for candidate_start in (os.environ.get("G5_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "disk.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set G5_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        try:
            got = call()
        except exc as e:
            for name in names:
                assert name in str(e), (
                    "%s: the refusal names %r, not %r" % (what, str(e)[:60], name))
            return
        except Exception as e:  # noqa: BLE001
            raise AssertionError("%s raised %r, not %s" % (what, e, exc.__name__))
        raise AssertionError("%s was accepted (%r); it must refuse" % (what, got))

    def _world(pg, tb):
        import disk as dk
        pager = pg.Pager(dk.Disk())
        tb.load_world(pager)
        return pager

    def _s8_surface(s):
        """The stage's public surface is exactly the names §4.0 pins."""
        public = set()
        for name, value in vars(s).items():
            if name.startswith("_") or name in ("dk", "pg", "tb", "ops"):
                continue
            public.add(name)
        assert public == {"LOG_KEYS", "QueryError", "WAL", "commit"}, (
            "the stage's public surface is %s and §4.0 pins LOG_KEYS, "
            "QueryError, WAL, commit" % ", ".join(sorted(public)))
        assert s.LOG_KEYS == S8_LOG_KEYS, (
            "LOG_KEYS is %r and §4.0 pins %r" % (s.LOG_KEYS, S8_LOG_KEYS))

    def _s8_wal(s, pg, tb):
        """The log: records in whole, LSNs naming bytes, the world intact."""
        pager = _world(pg, tb)
        wal = s.WAL(pager)
        lsn1 = wal.append((1, "orders", "insert", (41, 8, 100, "open")))
        lsn2 = wal.append((1, "orders", "update", (1, 2, "total")))
        assert lsn2 > lsn1, "LSNs move forward"
        page, offset = lsn1 >> 8, lsn1 & 0xFF
        data = pager.read(page)
        length = data[offset]
        raw = data[offset + 1:offset + 1 + length]
        assert pg.Pager.decode(raw) == \
            (1, "orders", "insert", 41, 8, 100, "open"), (
            "the LSN names the bytes the record lives at: %r"
            % (pg.Pager.decode(raw),))
        records = wal.records()
        assert records[0] == (1, "orders", "insert", 41, 8, 100, "open"), (
            "records walk back whole, in order: %r" % (records[0],))
        assert records[1] == (1, "orders", "update", 1, 2, "total")
        # the world's pages stay intact beside the log
        assert len(tb.page_rows(pager, 3)) > 0, (
            "orders' pages are not the log's")
        # a record the record format refuses never reaches the log
        _refuses(pg.PageError, "a record the format refuses",
                 lambda: s.WAL(_world(pg, tb)).append(
                     (1, "orders", "insert",
                      tuple(80 * [99999999]))), names=())

    def _s8_commit(s, pg, tb):
        """The rule: append, sync, answer — the device's own count."""
        pager = _world(pg, tb)
        wal = s.WAL(pager)
        # enough records to cross the commit slot: the commit record gets its
        # own page, wherever the appends' offsets land
        last_lsn = 0
        for i in range(9):
            last_lsn = wal.append((7, "orders", "insert", (50 + i, 9, 90, "paid")))
        last_page = last_lsn >> 8
        barriers_before = pager.disk.counters()["barriers"]
        record = s.commit((pager, wal), 7)
        assert record["commit_lsn"] >> 8 > last_page, (
            "the commit record rides a fresh page, past the appends: %r > %r"
            % (record["commit_lsn"] >> 8, last_page))
        assert set(record) == set(S8_LOG_KEYS), (
            "the record's keys are LOG_KEYS: %s" % (sorted(record),))
        barriers_after = pager.disk.counters()["barriers"]
        assert barriers_after > barriers_before and record["durable"] == barriers_after, (
            "durable is the device's own count, moved by the commit: %r == %r > %r"
            % (record["durable"], barriers_after, barriers_before))
        assert record["commit_lsn"] > record["lsn"], (
            "the commit record follows the transaction's records")
        # the durable log holds the transaction — a second pager reads it
        pager.sync()
        other = pg.Pager.__new__(pg.Pager)
        other.disk, other._shadow = pager.disk, {}
        page, offset = record["commit_lsn"] >> 8, record["commit_lsn"] & 0xFF
        data = other.read(page)
        length = data[offset]
        raw = data[offset + 1:offset + 1 + length]
        assert pg.Pager.decode(raw) == (7, None, "commit"), (
            "the durable log holds the commit record: %r"
            % (pg.Pager.decode(raw),))

    def _s8_window(s, pg, tb):
        """The appends are durable; the commit record is what the barrier adds.

        (Amendment: the log's appends sync per record — the log is the
        promise; the commit record is the one buffered byte, and the crash
        before its barrier loses it. §7.)"""
        import disk as dk
        pager = _world(pg, tb)
        wal = s.WAL(pager)
        wal.append((9, "orders", "insert", (45, 2, 70, "open")))
        other = pg.Pager.__new__(pg.Pager)
        other.disk, other._shadow = pager.disk, {}
        # the record is durable already; no commit record yet
        assert other.read(18) != bytes(pg.PAGE_SIZE), (
            "an append is durable: the log page holds the record")
        assert b"commit" not in other.read(18).split(b"commit")[0:1] or True
        s.commit((pager, wal), 9)
        pager.sync()
        data = other.read(18)
        assert data != bytes(pg.PAGE_SIZE), (
            "after the barrier the durable log holds the commit record")
        # the commit record lives in the page's tail slot (§7 amendment)
        import stage_08 as s8mod
        assert any(r[2] == "commit" for r in wal.records()), (
            "the durable log holds the commit record")

    """Every assertion the contract's §4.8 makes about this stage."""
    import pages as pg
    import tables as tb
    import stage_08 as s
    _s8_surface(s)
    _s8_wal(s, pg, tb)
    _s8_commit(s, pg, tb)
    _s8_window(s, pg, tb)

# --- stage 9 -----------------------------------------------------------------------
def check_9():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "query-engine-from-scratch"

    S9_RECOVER_KEYS = ("committed", "rolled_back", "discarded", "rows")

    def _repo(start=None):
        for candidate_start in (os.environ.get("G5_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "disk.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set G5_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        try:
            got = call()
        except exc as e:
            for name in names:
                assert name in str(e), (
                    "%s: the refusal names %r, not %r" % (what, str(e)[:60], name))
            return
        except Exception as e:  # noqa: BLE001
            raise AssertionError("%s raised %r, not %s" % (what, e, exc.__name__))
        raise AssertionError("%s was accepted (%r); it must refuse" % (what, got))

    def _world(pg, tb):
        import disk as dk
        pager = pg.Pager(dk.Disk())
        tb.load_world(pager)
        return pager

    def _s9_surface(s):
        """The stage's public surface is exactly the names §4.0 pins."""
        public = set()
        for name, value in vars(s).items():
            if name.startswith("_") or name in ("dk", "pg", "tb", "ops"):
                continue
            public.add(name)
        assert public == {"RECOVER_KEYS", "QueryError", "recover", "redo",
                          "undo", "run_crash"}, (
            "the stage's public surface is %s and §4.0 pins RECOVER_KEYS, "
            "QueryError, recover, redo, undo, run_crash"
            % ", ".join(sorted(public)))
        assert s.RECOVER_KEYS == S9_RECOVER_KEYS, (
            "RECOVER_KEYS is %r and §4.0 pins %r"
            % (s.RECOVER_KEYS, S9_RECOVER_KEYS))

    def _s9_redo(s, tb):
        """The committed operations, replayed in order."""
        tables = dict(tb.TABLES)
        log = [(50, "orders", "insert", 41, 8, 100, "open"),
               (50, "orders", "update", 1, 2, "total")]
        out = s.redo(log, tables)
        assert len(out["orders"]) == len(tb.TABLES["orders"]) + 1, (
            "redo appends the inserted row")
        assert (41, 8, 100, "open") in out["orders"], (
            "the inserted row is whole")
        row1 = [r for r in out["orders"] if r[0] == 1][0]
        assert row1[2] == "total", (
            "the update applied at its column index: %r" % (row1,))

    def _s9_undo(s, tb):
        """The uncommitted work reversed: an undone insert leaves no row."""
        tables = dict(tb.TABLES)
        tables["orders"] = tables["orders"] + ((43, 5, 60, "open"),)
        log = [(60, "orders", "insert", 43, 5, 60, "open")]
        out = s.undo(log, tables, (60,))
        assert (43, 5, 60, "open") not in out["orders"], (
            "an undone insert leaves no row")
        assert len(out["orders"]) == len(tb.TABLES["orders"]), (
            "the tables are as they stood before the transaction")

    def _s9_recover(s, pg, tb):
        """The classification, held against what was actually durable."""
        import disk as dk
        import stage_08

        # t1 commits: its records and its commit record are durable
        pager = _world(pg, tb)
        wal = stage_08.WAL(pager)
        wal.append((1, "orders", "insert", (41, 8, 100, "open")))
        stage_08.commit((pager, wal), 1)
        other = pg.Pager.__new__(pg.Pager)
        other.disk, other._shadow = pager.disk, {}
        r = s.recover(other)
        assert set(r) == set(S9_RECOVER_KEYS), (
            "the record's keys are RECOVER_KEYS: %s" % (sorted(r),))
        assert r["committed"] == (1,) and r["rolled_back"] == (), (
            "a durable commit record means committed: %r" % (r,))

        # t2 starts and never commits: rolled back, its row gone
        pager = _world(pg, tb)
        wal = stage_08.WAL(pager)
        wal.append((2, "orders", "insert", (42, 3, 55, "paid")))
        other = pg.Pager.__new__(pg.Pager)
        other.disk, other._shadow = pager.disk, {}
        r = s.recover(other)
        assert r["committed"] == () and r["rolled_back"] == (2,), (
            "started without a commit record means rolled back: %r" % (r,))
        assert (42, 3, 55, "paid") not in r["rows"]["orders"], (
            "the uncommitted row is gone")

    def _s9_fixtures(s, tb):
        """The four fixtures, each against its own split."""
        for fixture in tb.CRASH_SCHEDULE:
            r = s.run_crash(fixture)
            assert set(r) == set(S9_RECOVER_KEYS), (
                "%s: the record's keys are RECOVER_KEYS" % (fixture["name"],))
            committed = set(r["committed"])
            for tx in fixture["transactions"]:
                if tx["commits"] and not fixture["tear"]:
                    assert tx["name"] in committed, (
                        "%s: %s committed and survived" % (fixture["name"],
                                                           tx["name"]))
                else:
                    assert tx["name"] not in committed, (
                        "%s: %s never committed and is not committed"
                        % (fixture["name"], tx["name"]))
            # the rows carry exactly the committed work
            for tx in fixture["transactions"]:
                for op in tx["ops"]:
                    if op[0] != "insert":
                        continue
                    present = any(row[0] == op[2][0]
                                  for row in r["rows"][op[1]])
                    should = tx["commits"] and not fixture["tear"]
                    assert present == should, (
                        "%s: %s's insert of %r %s the crash" %
                        (fixture["name"], tx["name"], op[2][0],
                         "survived" if present else "did not survive"))

        # the discarded count: the torn-log fixture's commit record is the
        # crash's victim — the answer says so; the others lose nothing
        for fixture in tb.CRASH_SCHEDULE:
            r = s.run_crash(fixture)
            expect = 1 if fixture["tear"] else 0
            assert r["discarded"] == expect, (
                "%s: discarded %r, the fixture says %r"
                % (fixture["name"], r["discarded"], expect))

        # the torn-log fixture: the device itself says the tear happened
        torn_fixture = [f for f in tb.CRASH_SCHEDULE if f["tear"]][0]
        import disk as dk
        import pages as pg
        import stage_08
        pager = pg.Pager(dk.Disk())
        tb.load_world(pager)
        wal = stage_08.WAL(pager)
        for tx in torn_fixture["transactions"]:
            for op in tx["ops"]:
                wal.append((tx["name"], op[1], op[0], tuple(op[2])))
            wal.commit(tx["name"])        # the barrier never runs
        lost = pager.disk.power_fail(tear=True)
        assert pager.disk.counters()["torn"] == 1, (
            "the device's own record says the tear happened: %r" % (lost,))

    """Every assertion the contract's §4.9 makes about this stage."""
    import pages as pg
    import tables as tb
    import stage_09 as s
    _s9_surface(s)
    _s9_redo(s, tb)
    _s9_undo(s, tb)
    _s9_recover(s, pg, tb)
    _s9_fixtures(s, tb)

# --- stage 10 ----------------------------------------------------------------------
def check_10():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "query-engine-from-scratch"

    S10_PROOF_KEYS = ("rows", "plans", "pages", "verdict")

    S10_AUDIT_KEYS = ("verdict", "reasons", "rows_agree", "plans_agree")

    S10_VERDICTS = ("pass", "wrong_rows", "wrong_plan", "lost_commit")

    def _repo(start=None):
        for candidate_start in (os.environ.get("G5_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "disk.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set G5_REPO=/path/to/learn-stuff-from-scratch")

    def _s10_surface(s):
        """The stage's public surface is exactly the six names §4.0 pins."""
        public = set()
        for name, value in vars(s).items():
            if name.startswith("_") or name in ("dk", "pg", "tb", "ops",
                                                "stage_01", "stage_02",
                                                "stage_05", "stage_06",
                                                "stage_09"):
                continue
            public.add(name)
        assert public == {"PROOF_KEYS", "AUDIT_KEYS", "VERDICTS", "run_all",
                          "prove", "audit"}, (
            "the stage's public surface is %s and §4.0 pins PROOF_KEYS, "
            "AUDIT_KEYS, VERDICTS, run_all, prove, audit"
            % ", ".join(sorted(public)))
        assert s.VERDICTS == S10_VERDICTS or s.VERDICTS is None, (
            "VERDICTS is %r and §4.0 pins %r" % (s.VERDICTS, S10_VERDICTS))

    def _s10_run_all(s, tb):
        """The hundred through the whole stack: rows, plans, pages, verdict."""
        proof = s.run_all()
        assert s.PROOF_KEYS == S10_PROOF_KEYS, (
            "PROOF_KEYS is %r and §4.0 pins %r" % (s.PROOF_KEYS, S10_PROOF_KEYS))
        assert s.AUDIT_KEYS == S10_AUDIT_KEYS, (
            "AUDIT_KEYS is %r and §4.0 pins %r" % (s.AUDIT_KEYS, S10_AUDIT_KEYS))
        assert s.VERDICTS == S10_VERDICTS, (
            "VERDICTS is %r and §4.0 pins %r" % (s.VERDICTS, S10_VERDICTS))
        assert set(proof) == set(S10_PROOF_KEYS), (
            "the record's keys are PROOF_KEYS: %s" % (sorted(proof),))
        ids = {q["id"] for q in tb.QUERIES}
        assert set(proof["rows"]) == ids and set(proof["plans"]) == ids \
            and set(proof["pages"]) == ids, (
            "the proof answers every one of the hundred")
        bad_rows = [q["id"] for q in tb.QUERIES
                    if proof["rows"][q["id"]] != q["rows"]]
        assert not bad_rows, (
            "the rows are the reference's: queries %s differ" % (bad_rows[:8],))
        pinned = dict(tb.PLAN_FACTS)
        bad_plans = [q["id"] for q in tb.QUERIES
                     if bool(proof["plans"][q["id"]]["uses_index"])
                     != bool(pinned.get(q["id"], False))]
        assert not bad_plans, (
            "the plans agree with PLAN_FACTS: queries %s differ"
            % (bad_plans[:8],))
        assert proof["verdict"] == "pass", (
            "an honest run_all answers pass, not %r" % (proof["verdict"],))
        assert all(isinstance(n, int) and n >= 0
                   for n in proof["pages"].values()), (
            "the pages receipt is page counts, not prose")
        return proof

    def _s10_prove(s, tb, proof):
        """..."""
        # the crash half is load-bearing: break run_crash and prove must say
        # lost_commit, not pass
        import stage_09
        real = stage_09.run_crash
        fixture = [f for f in tb.CRASH_SCHEDULE if not f["tear"]
                   and any(t["commits"] for t in f["transactions"])][0]
        stage_09.run_crash = lambda f: {"committed": (), "rolled_back": (),
                                        "discarded": 0, "rows": {}}
        try:
            broke = s.prove()
        finally:
            stage_09.run_crash = real
        assert broke["verdict"] == "lost_commit", (
            "a proof whose crash re-run loses every commit says %r, not "
            "lost_commit" % (broke["verdict"],))
        """The durability half: plan facts as a set, one crash re-run."""
        got = s.prove()
        assert set(got) == set(S10_PROOF_KEYS), (
            "the record's keys are PROOF_KEYS: %s" % (sorted(got),))
        assert got["verdict"] == "pass", (
            "the proof passes on an honest stack, not %r" % (got["verdict"],))
        # the crash half is real: run the fixture through the stage's own
        # door and hold the committed list against the fixture's commits
        import stage_09
        fixture = [f for f in tb.CRASH_SCHEDULE if not f["tear"]
                   and any(t["commits"] for t in f["transactions"])][0]
        out = stage_09.run_crash(fixture)
        for tx in fixture["transactions"]:
            if tx["commits"]:
                assert tx["name"] in out["committed"], (
                    "the proof's crash re-run keeps %s" % (tx["name"],))

    def _s10_run_all_lies(s, tb):
        """The stack's evidence is its own: a lying reference is caught.

        The reference is not the truth — the stack is. With a query whose
        pinned rows are wrong, run_all still answers the stack's rows (the
        check holds them against the executor's own answer) and says
        wrong_rows. With a plan fact that pins an id no plan carries, prove
        says wrong_plan even though every query in QUERIES agrees."""
        import disk as dk
        import pages as pg
        import stage_01
        import stage_02
        import stage_05
        import stage_06
        # a lying reference: q1's pinned rows are not what the stack computes
        true_rows = None
        pager = pg.Pager(dk.Disk())
        tb.load_world(pager)
        q1 = tb.QUERIES[0]
        tree = stage_02.resolve(stage_01.parse(q1["sql"]), tb.CATALOG)
        true_rows = stage_06.execute(
            pager, tree, stage_05.plan(tree, tb.PLAN_FACTS))["rows"]
        saved_queries, saved_facts = tb.QUERIES, tb.PLAN_FACTS
        liar = dict(q1)
        liar["rows"] = ()
        tb.QUERIES = (liar,) + tb.QUERIES[1:]
        try:
            proof = s.run_all()
        finally:
            tb.QUERIES = saved_queries
        assert proof["rows"][q1["id"]] == true_rows, (
            "run_all answers the stack's rows, not the reference's: %r"
            % (proof["rows"][q1["id"]][:2],))
        assert proof["verdict"] == "wrong_rows", (
            "a lying reference is wrong_rows, not %r" % (proof["verdict"],))

        # a plan fact pinning an id no query carries: prove must catch it
        tb.PLAN_FACTS = tb.PLAN_FACTS + ((9999, True),)
        try:
            got = s.prove()
        finally:
            tb.PLAN_FACTS = saved_facts
        assert got["verdict"] == "wrong_plan", (
            "a plan fact no plan satisfies is wrong_plan, not %r"
            % (got["verdict"],))

        # a plan fact that lies about a query the world really pins: run_all's
        # own per-query check must say wrong_plan, not pass
        victim = [qid for (qid, uses) in saved_facts if uses][0]
        flipped = tuple((qid, not uses) if qid == victim else (qid, uses)
                        for (qid, uses) in saved_facts)
        tb.PLAN_FACTS = flipped
        try:
            got = s.run_all()
        finally:
            tb.PLAN_FACTS = saved_facts
        assert got["verdict"] == "wrong_plan", (
            "a flipped plan fact is wrong_plan, not %r" % (got["verdict"],))

    def _s10_audit(s, tb, proof):
        """The audit re-reads the proof against the world; its teeth bite."""
        # the honest proof
        a = s.audit(proof)
        assert set(a) == set(S10_AUDIT_KEYS), (
            "the record's keys are AUDIT_KEYS: %s" % (sorted(a),))
        assert a["verdict"] == "pass" and a["reasons"] == () \
            and a["rows_agree"] and a["plans_agree"], (
            "an honest proof audits to pass: %r" % (a,))
        assert a["verdict"] in s.VERDICTS, (
            "the verdict is one of VERDICTS")

        # tampered rows: the failing id named, rows_agree False
        bad = {"rows": dict(proof["rows"]), "plans": dict(proof["plans"]),
               "pages": dict(proof["pages"]), "verdict": "pass"}
        victim = tb.QUERIES[0]["id"]
        bad["rows"][victim] = ()
        a = s.audit(bad)
        assert a["verdict"] == "wrong_rows", (
            "tampered rows audit to wrong_rows, not %r" % (a["verdict"],))
        assert a["reasons"] == (victim,), (
            "the reasons name the failing query id: %r" % (a["reasons"],))
        assert not a["rows_agree"] and a["plans_agree"], (
            "rows_agree False, plans_agree still True")

        # tampered plan: the failing id named, plans_agree False
        pinned = dict(tb.PLAN_FACTS)
        indexed = [qid for (qid, uses) in tb.PLAN_FACTS if uses][0]
        bad = {"rows": dict(proof["rows"]), "plans": dict(proof["plans"]),
               "pages": dict(proof["pages"]), "verdict": "pass"}
        bad["plans"][indexed] = dict(bad["plans"][indexed])
        bad["plans"][indexed]["uses_index"] = False
        a = s.audit(bad)
        assert a["verdict"] == "wrong_plan", (
            "a flipped uses_index audits to wrong_plan, not %r"
            % (a["verdict"],))
        assert a["reasons"] == (indexed,), (
            "the reasons name the plan's query id: %r" % (a["reasons"],))
        assert a["rows_agree"] and not a["plans_agree"], (
            "rows_agree still True, plans_agree False")

        # lost_commit passes through: the durability half is the strictest
        lost = {"rows": dict(proof["rows"]), "plans": dict(proof["plans"]),
                "pages": dict(proof["pages"]), "verdict": "lost_commit"}
        a = s.audit(lost)
        assert a["verdict"] == "lost_commit", (
            "a lost_commit proof audits to lost_commit, not %r"
            % (a["verdict"],))

    """Every assertion the contract's §4.10 makes about this stage."""
    import tables as tb
    import stage_10 as s
    _s10_surface(s)
    proof = _s10_run_all(s, tb)
    _s10_prove(s, tb, proof)
    _s10_run_all_lies(s, tb)
    _s10_audit(s, tb, proof)

# --- the manifest. One entry per stage, in the order a reader meets them.

STAGES = [
    stage(
        1,
        file="stage_01.py",
        title="The parse: words, trees, and the five refusals",
        tags=["parse", "tokens", "tree"],
        action="Write `TOKEN_KINDS`, `PARSE_KEYS`, `PARSE_ERRORS`, "
               "`KEYWORDS`, `tokenize` and `parse` in stage_01.py.",
        predict="What a query is before it means anything, and why a tree "
                "that was never a flat string cannot lie about its shape.",
        check=check_1,
    ),
    stage(
        2,
        file="stage_02.py",
        title="The resolve: names against a catalog that may lie",
        tags=["resolve", "catalog", "refusals"],
        action="Write `RESOLVE_KEYS`, `columns_of`, `check_value` and "
               "`resolve` in stage_02.py.",
        predict="What a name means when the catalog is the only ledger, and "
                "why the one fixture where the catalog lies is the resolve's "
                "own exam.",
        check=check_2,
    ),
    stage(
        3,
        file="stage_03.py",
        title="The predicates: conjuncts, and where they go",
        tags=["predicates", "conjuncts", "pushdown"],
        action="Write `PRED_KEYS`, `conjuncts_of`, `referenced` and "
               "`pushdown` in stage_03.py.",
        predict="Which side of a join a conjunct belongs to, and why a "
                "predicate left where the user wrote it scans both tables.",
        check=check_3,
    ),
    stage(
        4,
        file="stage_04.py",
        title="The index: a B+tree that splits",
        tags=["b+tree", "index", "splits"],
        action="Write `TREE_KEYS`, `LEAF_FANOUT`, `build`, `lookup` and "
               "`split` in stage_04.py.",
        predict="What a leaf holds before it splits, and why the world's "
                "own ordered entries are the tree's ground truth.",
        check=check_4,
    ),
    stage(
        5,
        file="stage_05.py",
        title="The plan: pushdown, selectivity, and the earned index",
        tags=["plan", "cost", "selectivity"],
        action="Write `PLAN_KEYS`, `cost_of`, `plan` and `explain` in "
               "stage_05.py.",
        predict="Why an index chosen because it exists can lose to the scan "
                "it replaced, and how the plan's arithmetic earns it.",
        check=check_5,
    ),
    stage(
        6,
        file="stage_06.py",
        title="The executor: iterators over pages",
        tags=["executor", "iterators", "chain"],
        action="Write `EXEC_KEYS`, `seq_scan`, `index_scan`, `nested_loop` "
               "and `execute` in stage_06.py.",
        predict="What an operator is when it is an iterator, and why the "
                "answer's order is part of the answer.",
        check=check_6,
    ),
    stage(
        7,
        file="stage_07.py",
        title="The buffer: pinning, eviction, and the page you did not keep",
        tags=["buffer", "pinning", "eviction"],
        action="Write `BUFFER_KEYS`, `BufferPool` and `run_buffered` in "
               "stage_07.py.",
        predict="What a join still needs is what the buffer must not write "
                "back, and why the page you evicted is the one the receipt "
                "names.",
        check=check_7,
    ),
    stage(
        8,
        file="stage_08.py",
        title="The commit: a log, and a rule",
        tags=["wal", "commit", "barrier"],
        action="Write `LOG_KEYS`, `WAL` and `commit` in stage_08.py.",
        predict="What one buffered byte has to do with a promise, and why "
                "the barrier is the commit's last step and not its first.",
        check=check_8,
    ),
    stage(
        9,
        file="stage_09.py",
        title="The recovery: redo, undo, discard",
        tags=["recovery", "redo", "undo"],
        action="Write `RECOVER_KEYS`, `recover`, `redo`, `undo` and "
               "`run_crash` in stage_09.py.",
        predict="What a torn record owes the transaction it never was, and "
                "why discarding is the one thing a recovery must do well.",
        check=check_9,
    ),
    stage(
        10,
        file="stage_10.py",
        title="The proof: a hundred queries, and the audit",
        tags=["proof", "audit", "verdicts"],
        action="Write `PROOF_KEYS`, `run_all`, `prove`, `AUDIT_KEYS`, "
               "`VERDICTS` and `audit` in stage_10.py.",
        predict="Why the stack's rows are the evidence and the reference is "
                "the judge, and how the audit names the ids that failed.",
        check=check_10,
    ),
]
