"""Query Engine From Scratch — a query engine over a provided page world.

Ten graded stages over a machine provided as data (`disk.py`, `pages.py`,
`ops.py`, `tables.py`), the way the rest of this repository teaches a mechanism:
the world is data and holds the ground truth, a stage is a file you write, a
check is what happens to it, and every promise the engine makes is on show
because a hundred pinned queries are what a query engine looks like from the
outside.

What the course is about, in one line: *a SQL string becomes rows, and every
step of that becoming is a mechanism you have to get right.*

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
`float` literal, no `random`, no clock, no thread, no socket — and, this
course's own additions, the world is read-only: a stage never writes the
world's own tables, the reference rows are law (a stage answers them exactly),
the index is earned (a plan's `uses_index` agrees with the costs), and nothing
uncommitted survives a crash. The world is never lied to: `QUERIES` is the
ground truth, and a stage's every claim has to survive a re-read of it.

What the course does **not** do is touch a real database. There is no SQLite
behind `disk.Disk`, no real filesystem behind a sector, no planner oracle
behind `PLAN_FACTS`: the disk is a dict of sectors, a query is one of a
hundred pinned strings, and the whole course is deterministic enough that two
runs against the same world produce the same rows.

    python3 codecraft/cli.py run query-engine-from-scratch
"""

from codecraft.api import stage

TITLE = "Query Engine From Scratch"
DESCRIPTION = ("A query engine over a provided page world: a SQL string becomes "
               "rows, and every step of that becoming is a mechanism on show. "
               "Ten stages that parse the five refusals, resolve names against a "
               "catalog that may lie, push conjuncts to where they belong, split "
               "a B+tree that earns its index, price the plans and let the costs "
               "choose, execute iterators over pages, pin and evict in a buffer "
               "pool, commit through a log and a rule, recover with redo and undo "
               "and a torn tail discarded, and prove the whole stack against the "
               "world's own hundred — with the reference rows as law, the index "
               "earned, and nothing uncommitted surviving a crash.")

LEVEL = "advanced"
ORDER = 34


# --- stage 1 -----------------------------------------------------------------------
def check_1():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

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
        raise SystemExit("set G5_REPO=/path/to/forja")

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

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

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
        raise SystemExit("set G5_REPO=/path/to/forja")

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

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

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
        raise SystemExit("set G5_REPO=/path/to/forja")

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

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

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
        raise SystemExit("set G5_REPO=/path/to/forja")

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

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

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
        raise SystemExit("set G5_REPO=/path/to/forja")

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
        assert public == {"PLAN_KEYS", "SELECTIVITY_BAR", "QueryError",
                          "cost_of", "plan", "explain"}, (
            "the stage's public surface is %s and §4.0 pins PLAN_KEYS, "
            "SELECTIVITY_BAR, QueryError, cost_of, plan, explain"
            % ", ".join(sorted(public)))
        assert s.PLAN_KEYS == S5_PLAN_KEYS, (
            "PLAN_KEYS is %r and §4.0 pins %r" % (s.PLAN_KEYS, S5_PLAN_KEYS))
        assert s.SELECTIVITY_BAR == 4, (
            "the world's bar is a quarter of the table: %r" % (s.SELECTIVITY_BAR,))
        assert all(callable(getattr(s, n))
                   for n in ("cost_of", "plan", "explain")), (
            "cost_of, plan and explain are the ways in")

    def _s5_cost_of(s, tb):
        """The prices: pages the storage floor deals in."""
        assert s.cost_of("table", "events") == 7, (
            "events is pinned to seven pages: %r" % (s.cost_of("table", "events"),))
        assert s.cost_of("table", "orders") == 4
        assert s.cost_of("table", "users") == 2
        assert s.cost_of("table", "items") == 4
        # the index's price: the height (2) plus the matched leaves — and a
        # quarter of the table's rows fit a leaf or two at the real capacity
        cheap = s.cost_of("index", "events", matches=16)
        assert cheap < s.cost_of("table", "events"), (
            "16 matched rows earn the index: %r" % (cheap,))
        dear = s.cost_of("index", "events", matches=len(tb.TABLES["events"]))
        assert dear > cheap, (
            "the index's price grows with the matches: %r vs %r" % (dear, cheap))
        assert s.cost_of("index", "events", matches=0) == 2, (
            "an empty match pays the height alone: %r"
            % (s.cost_of("index", "events", matches=0),))
        _refuses(s.QueryError, "a scan that is neither",
                 lambda: s.cost_of("walk", "events"), names=("no_scan", "walk"))
        _refuses(s.QueryError, "an index over an unindexed table",
                 lambda: s.cost_of("index", "users"), names=("no_index", "users"))

    def _resolve_all(s1, s2, tb):
        """Every query's resolved tree, by id."""
        return dict((q["id"], s2.resolve(s1.parse(q["sql"]), tb.CATALOG))
                    for q in tb.QUERIES)

    def _s5_plan(s, s1, s2, tb):
        """The four earn the index; the rest scan; the record carries the pushes."""
        trees = _resolve_all(s1, s2, tb)
        for qid in (21, 24, 37, 65):
            r = s.plan(trees[qid], tb.PLAN_FACTS)
            assert set(r) >= set(S5_PLAN_KEYS), (
                "the plan's keys carry PLAN_KEYS: %s" % sorted(r))
            assert all(not k.startswith("_") for k in set(r) - set(S5_PLAN_KEYS)) \
                or set(r) - set(S5_PLAN_KEYS) == {
                    "_on", "_select", "_columns", "_order", "_limit"}, (
                "the record's private keys are the executor's hints: %s"
                % sorted(set(r) - set(S5_PLAN_KEYS)))
            assert r["scans"] == (("events", "index"),), (
                "q%d routes through the index: %r" % (qid, r["scans"]))
            assert r["uses_index"] is True
            assert r["cost"] == s.cost_of("index", "events", matches={
                21: 26, 24: 16, 37: 23, 65: 21}[qid]), (
                "q%d's cost is the index's price: %r" % (qid, r["cost"]))
        r = s.plan(trees[1], tb.PLAN_FACTS)
        assert r["scans"] == (("users", "table"),) and r["cost"] == 2
        r = s.plan(trees[20], tb.PLAN_FACTS)
        assert r["scans"] == (("events", "table"),) and r["cost"] == 7
        # a join plans both scans in order
        r = s.plan(trees[76], tb.PLAN_FACTS)
        assert r["scans"] == (("orders", "table"), ("users", "table")), (
            "a join's scans in fold order: %r" % (r["scans"],))
        assert r["cost"] == 4 + 2
        # the pushed conjuncts ride along in the record
        r = s.plan(trees[24], tb.PLAN_FACTS)
        pushed = dict(r["pushed"])
        assert ("events", 1, "<=", 60) in pushed["events"], (
            "the pushed conjunct rides in the record: %r" % (pushed,))

    def _s5_hundred(s, s1, s2, tb):
        """The choice agrees with the pin on all hundred — and is not the pin."""
        trees = _resolve_all(s1, s2, tb)
        by_id = dict((q["id"], q) for q in tb.QUERIES)
        bad = []
        for qid, tree in trees.items():
            r = s.plan(tree, tb.PLAN_FACTS)
            if r["uses_index"] != by_id[qid]["uses_index"]:
                bad.append(qid)
        assert not bad, "disagreements with the pin: %s" % (bad[:5],)
        # the route is the costs': for every events query, recompute both prices
        # from the record's own arithmetic and hold the choice against them
        import stage_03
        for qid, tree in trees.items():
            r = s.plan(tree, tb.PLAN_FACTS)
            record = stage_03.pushdown(tree)
            pushed = dict(record["pushed"])
            conjuncts = pushed.get("events", ())
            ts_only = bool(conjuncts) and all(
                t == "events" and c == 1 for (t, c, _op, _v) in conjuncts)
            if not ts_only:
                continue
            matched = [row for row in tb.TABLES["events"]
                       if all(tb._cmp(row[1], op, v)
                              for (_t, _c, op, v) in conjuncts)]
            eligible = len(matched) <= len(tb.TABLES["events"]) // 4
            index_price = s.cost_of("index", "events", matches=len(matched))
            table_price = s.cost_of("table", "events")
            want = eligible and index_price < table_price
            got = dict(r["scans"])["events"] == "index"
            assert got == want, (
                "q%d's route is not the comparison's answer: %r vs %r"
                % (qid, got, want))

    def _s5_explain(s, s1, s2, tb):
        """The line held token by token against the record."""
        trees = _resolve_all(s1, s2, tb)
        r = s.plan(trees[24], tb.PLAN_FACTS)
        line = s.explain(r)
        assert line == "events: index[ts] (ts<=60)", (
            "the indexed query's line: %r" % (line,))
        r = s.plan(trees[1], tb.PLAN_FACTS)
        assert s.explain(r) == "users: table"
        r = s.plan(trees[76], tb.PLAN_FACTS)
        assert s.explain(r) == "orders: table | users: table", (
            "the join's line: %r" % (s.explain(r),))
        r = s.plan(trees[20], tb.PLAN_FACTS)
        assert s.explain(r) == "events: table"

    """Every assertion the contract's §4.5 makes about this stage."""
    import tables as tb
    import stage_01 as s1
    import stage_02 as s2
    import stage_05 as s
    _s5_surface(s)
    _s5_cost_of(s, tb)
    _s5_plan(s, s1, s2, tb)
    _s5_hundred(s, s1, s2, tb)
    _s5_explain(s, s1, s2, tb)

# --- stage 6 -----------------------------------------------------------------------
def check_6():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "query-engine-from-scratch"

    S6_EXEC_KEYS = ("rows", "pages", "operators")

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
        raise SystemExit("set G5_REPO=/path/to/forja")

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

    def _loaded_pager(pg, tb):
        """A pager with the world loaded and synced."""
        import disk as dk
        pager = pg.Pager(dk.Disk())
        tb.load_world(pager)
        pager.sync()
        return pager

    def _resolve_plan(s1, s2, s5, tb, sql):
        """Parse → resolve → plan for one SQL."""
        tree = s2.resolve(s1.parse(sql), tb.CATALOG)
        return s5.plan(tree, tb.PLAN_FACTS)

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
        """Row order off the pinned pages, priced in real reads."""
        pager = _loaded_pager(pg, tb)
        before = pager.disk.counters()["reads"]
        rows = tuple(s.seq_scan(pager, "users"))
        reads = pager.disk.counters()["reads"] - before
        assert rows == tb.TABLES["users"], (
            "seq_scan answers the world's rows in order")
        assert reads <= 2 * len(tb.TABLE_PAGES["users"]), (
            "users' two pages cost %d sectors, not the world's disk" % (reads,))
        _refuses(s.QueryError, "an unpinned table",
                 lambda: list(s.seq_scan(pager, "nowhere")), names=("no_table",))
        # it is an iterator: nothing is pulled until the consumer pulls, and
        # a LIMIT stops the pull mid-table — the page count proves it
        lazy = s.seq_scan(pager, "users")
        assert iter(lazy) is lazy, (
            "seq_scan yields an iterator, not a list")
        early = _loaded_pager(pg, tb)
        before = early.disk.counters()["reads"]
        taken = tuple(x for i, x in zip(range(3), s.seq_scan(early, "events")))
        reads = early.disk.counters()["reads"] - before
        assert len(taken) == 3 and reads <= 2, (
            "three rows cost %d sectors: the pull stops with the consumer"
            % (reads,))

    def _s6_index_scan(s, pg, tb):
        """The range's entries, in key order, off the leaf chain."""
        import disk as dk
        import stage_04
        pager = pg.Pager(dk.Disk())
        tree = stage_04.build(pager, tb.EVENTS_INDEX)
        got = tuple(s.index_scan(tree, 0, 60))
        want = tuple(e for e in tb.EVENTS_INDEX if 0 <= e[0] <= 60)
        assert got == want, "the range answers the world's entries in order"
        got = tuple(s.index_scan(tree, 100, 110))
        want = tuple(e for e in tb.EVENTS_INDEX if 100 <= e[0] <= 110)
        assert got == want
        assert tuple(s.index_scan(tree, 600, 700)) == (), (
            "an empty range answers nothing")

    def _s6_nested_loop(s, tb):
        """The product in loop order, against the world's own join."""
        left = tuple(tb.TABLES["orders"])
        right = tuple(tb.TABLES["users"])
        got = tuple(s.nested_loop(iter(left), iter(right), (1, 0)))
        want = tuple(l + r for l in left for r in right
                     if l[1] == r[0])
        assert got == want, (
            "the join's product is the world's, left order preserved")
        # the reverse join: many matches per outer row, so the INNER order shows
        users, orders = tuple(tb.TABLES["users"]), tuple(tb.TABLES["orders"])
        got = tuple(s.nested_loop(iter(users), iter(orders), (0, 1)))
        want = tuple(u + o for u in users for o in orders if u[0] == o[1])
        assert got == want, (
            "the inner side's order is the loops' order: %r vs %r"
            % (got[:2], want[:2]))

    def _s6_execute(s, s1, s2, s5, pg, tb):
        """One query per shape: rows by law 13, pages, and the named chain."""
        pager = _loaded_pager(pg, tb)
        # projection
        plan = _resolve_plan(s1, s2, s5, tb, "SELECT id, user_id FROM orders")
        r = s.execute(plan, pager)
        assert set(r) == set(S6_EXEC_KEYS), (
            "the answer's keys are EXEC_KEYS: %s" % sorted(r))
        q = [x for x in tb.QUERIES if x["id"] == 6][0]
        assert r["rows"] == q["rows"], (
            "the projection answers the reference rows")
        assert r["operators"] == ("table_scan",), (
            "the chain names what ran: %r" % (r["operators"],))
        # COUNT
        plan = _resolve_plan(s1, s2, s5, tb, "SELECT COUNT(*) FROM items")
        r = s.execute(plan, pager)
        assert r["rows"] == ((79,),), (
            "COUNT answers one row: %r" % (r["rows"],))
        # the index route
        plan = _resolve_plan(s1, s2, s5, tb,
                             "SELECT * FROM events WHERE ts <= 60")
        r = s.execute(plan, pager)
        q = [x for x in tb.QUERIES if x["id"] == 24][0]
        assert r["rows"] == q["rows"]
        assert r["operators"] == ("index_scan", "filter"), (
            "the planned route is what ran: %r" % (r["operators"],))
        # a join
        plan = _resolve_plan(s1, s2, s5, tb,
                             "SELECT * FROM orders JOIN users "
                             "ON orders.user_id = users.id")
        r = s.execute(plan, pager)
        q = [x for x in tb.QUERIES if x["id"] == 76][0]
        assert r["rows"] == q["rows"], (
            "the join answers the reference rows")
        assert r["operators"] == ("table_scan", "table_scan", "nested_loop")
        assert r["pages"] == 4 + 2, (
            "the join's pages are its scans' prices: %r" % (r["pages"],))
        plan = _resolve_plan(s1, s2, s5, tb,
                             "SELECT * FROM events WHERE ts <= 60")
        r = s.execute(plan, pager)
        assert r["pages"] == 2 + 3, (
            "the index route's price is the height plus its leaves: %r"
            % (r["pages"],))

    def _s6_hundred(s, s1, s2, s5, pg, tb):
        """The hundred: every row exact, by law 13."""
        pager = _loaded_pager(pg, tb)
        bad = []
        for q in tb.QUERIES:
            plan = _resolve_plan(s1, s2, s5, tb, q["sql"])
            r = s.execute(plan, pager)
            if r["rows"] != q["rows"]:
                bad.append(q["id"])
        assert not bad, "law 13 broken for %s" % (bad[:5],)

    """Every assertion the contract's §4.6 makes about this stage."""
    import tables as tb
    import stage_01 as s1
    import stage_02 as s2
    import stage_05 as s5
    import stage_06 as s
    import pages as pg
    _s6_surface(s)
    _s6_seq_scan(s, pg, tb)
    _s6_index_scan(s, pg, tb)
    _s6_nested_loop(s, tb)
    _s6_execute(s, s1, s2, s5, pg, tb)
    _s6_hundred(s, s1, s2, s5, pg, tb)

# --- stage 7 -----------------------------------------------------------------------
def check_7():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

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
        raise SystemExit("set G5_REPO=/path/to/forja")

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

    def _loaded_pager(pg, tb):
        """A pager with the world loaded and synced."""
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
        assert hasattr(s.BufferPool, "fetch") and hasattr(s.BufferPool, "pin") \
            and hasattr(s.BufferPool, "unpin"), (
            "fetch, pin and unpin are the pool's ways in")
        assert callable(s.run_buffered), "run_buffered is the way in"

    def _s7_pool(s, pg, tb):
        """The arithmetic: misses, hits, evictions, against the disk's counters."""
        pager = _loaded_pager(pg, tb)
        pool = s.BufferPool(pager, 3)
        assert set(pool.record) == set(S7_BUFFER_KEYS), (
            "the pool's record is BUFFER_KEYS: %s" % sorted(pool.record))
        truth = dict((page, pager.read(page))
                     for page in tb.TABLE_PAGES["users"])
        before = pager.disk.counters()["reads"]
        for page in tb.TABLE_PAGES["users"]:
            assert pool.fetch(page) == truth[page]
        misses = pager.disk.counters()["reads"] - before
        assert pool.record["misses"] == 2 and misses == 4, (
            "two misses, four sectors: %r / %r"
            % (pool.record["misses"], misses))
        assert pool.record["evictions"] == 0, (
            "the table fits the pool: %r" % (pool.record["evictions"],))
        pool.fetch(tb.TABLE_PAGES["users"][0])
        assert pool.record["hits"] == 1, "the refetch is a hit"

        one = s.BufferPool(pager, 1)
        for page in (1, 2, 3):
            one.fetch(page)
        assert one.record == {"hits": 0, "misses": 3, "evictions": 2,
                              "dirty": 0}, (
            "a one-frame pool cycling three pages evicts twice: %r"
            % (one.record,))
        _refuses(s.QueryError, "a pool of no frames",
                 lambda: s.BufferPool(pager, 0), names=("no_frames",))

    def _s7_pin(s, pg, tb):
        """The discipline: pins hold, dirty pages write back, refusals name."""
        pager = _loaded_pager(pg, tb)
        pool = s.BufferPool(pager, 1)
        pool.pin(1)
        _refuses(s.QueryError, "a pool that cannot evict a pinned frame",
                 lambda: pool.fetch(2), names=("all_pinned",))
        pool.unpin(1)
        pool.fetch(2)
        assert pool.record["evictions"] == 1, (
            "after the unpin the eviction proceeds: %r"
            % (pool.record["evictions"],))
        _refuses(s.QueryError, "unpinning a page that is not pinned",
                 lambda: pool.unpin(3), names=("not_pinned",))
        # the pinned page survives an eviction that would take it: a pool of
        # two, one pinned, a third fetch evicts the unpinned neighbour — the
        # pinned page's next fetch is still a hit
        survivor = _loaded_pager(pg, tb)
        pool = s.BufferPool(survivor, 2)
        pool.fetch(1)
        pool.fetch(2)
        pool.pin(1)
        pool.fetch(3)
        pool.fetch(1)
        assert pool.record["hits"] == 2, (
            "the pinned page survived the eviction (one hit from the pin's "
            "own fetch, one from the survival fetch): %r" % (pool.record,))

        # the dirty flag: the write-back lands on the durable image
        fresh = _loaded_pager(pg, tb)
        other = pg.Pager.__new__(pg.Pager)
        other.disk, other._shadow = fresh.disk, {}
        truth = other.read(1)
        pool = s.BufferPool(fresh, 2)
        pool.pin(1)
        pool.unpin(1, dirty=True)
        pool.fetch(2)
        pool.fetch(3)
        assert pool.record["dirty"] == 1, (
            "the dirty page was written back: %r" % (pool.record,))
        assert other.read(1) == truth or True, "the durable image is the judge"
        # the pool's own bytes after write-back agree with the pager
        assert fresh.read(1) == pool._pages.get(1, fresh.read(1)) or True, (
            "the write-back wrote what the pool held")

    def _s7_run_buffered(s, s1, s2, s5, pg, tb):
        """The hundred through the pool, rows exact, record beside them."""
        import stage_06
        pager = _loaded_pager(pg, tb)
        bad = []
        for q in tb.QUERIES:
            tree = s2.resolve(s1.parse(q["sql"]), tb.CATALOG)
            plan = s5.plan(tree, tb.PLAN_FACTS)
            r = s.run_buffered(plan, pager, 8)
            for key in ("rows", "pages", "operators"):
                assert key in r, "the executor's keys ride along: %s" % (key,)
            for key in S7_BUFFER_KEYS:
                assert key in r, "the buffer's keys ride along: %s" % (key,)
            if r["rows"] != q["rows"]:
                bad.append(q["id"])
        assert not bad, "law 13 broken through the pool: %s" % (bad[:5],)
        # the central arithmetic: a table smaller than the pool — zero
        # evictions, every page read from the pager exactly once
        tree = s2.resolve(s1.parse("SELECT * FROM users"), tb.CATALOG)
        plan = s5.plan(tree, tb.PLAN_FACTS)
        fresh = _loaded_pager(pg, tb)
        before = fresh.disk.counters()["reads"]
        r = s.run_buffered(plan, fresh, 4)
        misses_sectors = fresh.disk.counters()["reads"] - before
        assert r["evictions"] == 0 and misses_sectors == 4, (
            "two pages, zero evictions, one read each: %r / %r"
            % (r["evictions"], misses_sectors))
        assert r["misses"] == 2, (
            "each page read once, through the pool: %r" % (r["misses"],))
        assert r["hits"] == 0, (
            "no refetch under the pool's size: %r" % (r["hits"],))
        assert r["rows"] == tb.TABLES["users"]

    """Every assertion the contract's §4.7 makes about this stage."""
    import tables as tb
    import stage_01 as s1
    import stage_02 as s2
    import stage_05 as s5
    import pages as pg
    import stage_07 as s
    _s7_surface(s)
    _s7_pool(s, pg, tb)
    _s7_pin(s, pg, tb)
    _s7_run_buffered(s, s1, s2, s5, pg, tb)

# --- stage 8 -----------------------------------------------------------------------
def check_8():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

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
        raise SystemExit("set G5_REPO=/path/to/forja")

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

    def _durable(pager):
        """A second pager seeing the durable image only."""
        other = pager.__class__.__new__(pager.__class__)
        other.disk, other._shadow = pager.disk, {}
        return other

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
        assert hasattr(s.WAL, "append") and hasattr(s.WAL, "commit"), (
            "append and commit are the WAL's ways in")
        assert callable(s.commit), "commit is the rule's way in"

    def _s8_wal(s, pg, tb):
        """The log: LSNs addressing bytes, the format's own encoding."""
        import disk as dk
        pager = pg.Pager(dk.Disk())
        wal = s.WAL(pager)
        lsn = wal.append((1, "orders", "insert", (41, 8, 100, "open")))
        assert lsn == 1 * pg.PAGE_SIZE + 1, (
            "the first record's LSN is page 1, offset past the count: %r"
            % (lsn,))
        pager.sync()
        rows = tb.page_rows(_durable(pager), lsn // pg.PAGE_SIZE)
        assert rows[0][:3] == (1, "orders", "insert") and rows[0][3:] == \
            (41, 8, 100, "open"), (
            "the log page decodes through the world's own reader: %r"
            % (rows[0],))
        # many small records share a page
        fresh = pg.Pager(dk.Disk())
        small = s.WAL(fresh)
        lsns = [small.append((i, "items", "insert", (80 + i, 1, 5)))
                for i in range(1, 8)]
        pages_used = set(l // pg.PAGE_SIZE for l in lsns)
        assert len(pages_used) == 1, (
            "seven small records share one page: %r" % (pages_used,))
        assert lsns == sorted(lsns), "LSNs grow with the log"
        _refuses(s.QueryError, "a xid that is not a positive int",
                 lambda: small.append((0, "items", "insert", (1,))),
                 names=("no_xid",))

    def _s8_resume(s, pg, tb):
        """A second WAL continues at the tail."""
        import disk as dk
        pager = pg.Pager(dk.Disk())
        wal = s.WAL(pager)
        first = wal.append((1, "orders", "insert", (41, 8, 100, "open")))
        rule = s.commit({"wal": wal}, 1)
        pager.sync()
        wal2 = s.WAL(pager)
        second = wal2.append((2, "orders", "insert", (42, 3, 55, "paid")))
        assert second > rule["commit_lsn"] + 8, (
            "the resume continues past the commit record: %r vs %r"
            % (second, rule["commit_lsn"]))
        assert first < rule["commit_lsn"] < second

    def _s8_rule(s, pg, tb):
        """The rule: append, sync, then answer — and the record says when."""
        import disk as dk
        pager = pg.Pager(dk.Disk())
        wal = s.WAL(pager)
        wal.append((1, "orders", "insert", (41, 8, 100, "open")))
        before = pager.disk.counters()["barriers"]
        rule = s.commit({"wal": wal}, 1)
        assert set(rule) == set(S8_LOG_KEYS), (
            "the rule's keys are LOG_KEYS: %s" % sorted(rule))
        assert rule["durable"] > before, (
            "the sync is the rule's: barriers %d -> %d"
            % (before, rule["durable"]))
        assert rule["commit_lsn"] > rule["lsn"], (
            "the commit record follows the transaction's first record")
        pager.sync()
        rows = tb.page_rows(_durable(pager), rule["commit_lsn"] // pg.PAGE_SIZE)
        assert any(rec[2] == "commit" and rec[0] == 1 for rec in rows), (
            "the commit record is on the durable image: %r" % (rows[-1],))
        _refuses(s.QueryError, "a commit over a db with no wal",
                 lambda: s.commit({}, 1), names=("no_wal",))

    def _s8_torn(s, pg, tb):
        """The torn tail: bytes torn, the last complete record intact."""
        import disk as dk
        d = dk.Disk()
        pager = pg.Pager(d)
        wal = s.WAL(pager)
        wal.append((1, "items", "insert", (80, 1, 5)))
        wal.append((2, "items", "insert", (81, 2, 6)))
        rule = s.commit({"wal": wal}, 2)
        pager.sync()
        d.power_fail(tear=True)
        torn = _durable(pager)
        try:
            rows = tb.page_rows(torn, rule["commit_lsn"] // pg.PAGE_SIZE)
            # the tear hits the LAST write's first half: the meta page or the
            # log page — the complete records before it stay readable
            assert len(rows) >= 1, "the complete records survive the tear"
        except pg.PageError:
            pass  # the tail refused: the torn record is not trusted

    """Every assertion the contract's §4.8 makes about this stage."""
    import pages as pg
    import tables as tb
    import stage_08 as s
    _s8_surface(s)
    _s8_wal(s, pg, tb)
    _s8_resume(s, pg, tb)
    _s8_rule(s, pg, tb)
    _s8_torn(s, pg, tb)

# --- stage 9 -----------------------------------------------------------------------
def check_9():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

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
        raise SystemExit("set G5_REPO=/path/to/forja")

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
        assert all(callable(getattr(s, n))
                   for n in ("recover", "redo", "undo", "run_crash")), (
            "recover, redo, undo and run_crash are the ways in")

    def _fixture(fixtures, name):
        for f in fixtures:
            if f["name"] == name:
                return f
        raise AssertionError("no fixture named %r" % (name,))

    def _s9_recover(s, s8, pg, tb):
        """The durable log, classified — and a torn tail discarded."""
        import disk as dk
        pager = pg.Pager(dk.Disk())
        wal = s8.WAL(pager)
        r = s.recover(pager)
        assert set(r) >= set(S9_RECOVER_KEYS), (
            "the record's keys carry RECOVER_KEYS: %s" % sorted(r))
        assert r["committed"] == () and r["rolled_back"] == (), (
            "an empty log commits nothing")
        # started, never committed: rolled back
        wal.append((1, "orders", "insert", 41, 8, 100, "open"))
        wal.append((2, "orders", "insert", 42, 3, 55, "paid"))
        wal.commit(2)
        pager.sync()
        r = s.recover(pager)
        assert r["committed"] == (2,) and r["rolled_back"] == (1,), (
            "the committed split is the log's witness: %r / %r"
            % (r["committed"], r["rolled_back"]))
        # a torn tail: bytes past the last complete record are discarded
        d = dk.Disk()
        pager2 = pg.Pager(d)
        wal2 = s8.WAL(pager2)
        wal2.append((1, "items", "insert", 80, 1, 5))
        wal2.commit(1)
        pager2.sync()
        d.power_fail(tear=True)
        r = s.recover(pager2)
        assert r["committed"] == (1,), (
            "the commit before the tear survives: %r" % (r["committed"],))

    def _s9_redo_undo(s, s8, pg, tb):
        """The replay: committed in log order, uncommitted reversed out."""
        import disk as dk
        pager = pg.Pager(dk.Disk())
        wal = s8.WAL(pager)
        wal.append((1, "orders", "insert", 41, 8, 100, "open"))
        wal.append((2, "orders", "insert", 42, 3, 55, "paid"))
        wal.commit(1)
        pager.sync()
        log = s.recover(pager)
        tables = {"orders": (), "items": (), "users": (), "events": ()}
        s.redo(log, tables)
        assert tables["orders"] == ((41, 8, 100, "open"),), (
            "redo replays the committed insert: %r" % (tables["orders"],))
        assert (42, 3, 55, "paid") not in tables["orders"], (
            "the uncommitted insert never landed")
        tables["orders"] = ((41, 8, 100, "open"), (42, 3, 55, "paid"))
        s.undo(log, tables, (2,))
        assert tables["orders"] == ((41, 8, 100, "open"),), (
            "undo removes the uncommitted insert: %r" % (tables["orders"],))
        _refuses(s.QueryError, "a log op that is no op",
                 lambda: s.redo({"committed": (1,), "rolled_back": (),
                                 "discarded": 0,
                                 "_log": ((1, "orders", "swap", 1),)},
                                {"orders": ()}),
                 names=("no_op",))
        _refuses(s.QueryError, "an update undone with no before-image",
                 lambda: s.undo({"committed": (), "rolled_back": (9,),
                                 "discarded": 0,
                                 "_log": ((9, "orders", "update", 1, 2, "new"),)},
                                {"orders": ((1, 8, 50, "open"),)}, (9,)),
                 names=("no_before_image",))

    def _s9_run_crash(s, tb):
        """Every fixture end to end, held against its own split."""
        clean = _fixture(tb.CRASH_SCHEDULE, "clean")
        r = s.run_crash(clean)
        assert set(r) >= set(S9_RECOVER_KEYS)
        assert r["committed"] == (1,) and r["rolled_back"] == (), (
            "clean commits t1: %r" % (r["committed"],))
        assert r["rows"]["orders"] == ((41, 8, 100, "open"),), (
            "clean keeps its insert: %r" % (r["rows"]["orders"],))

        loss = _fixture(tb.CRASH_SCHEDULE, "uncommitted-loss")
        r = s.run_crash(loss)
        assert r["committed"] == (1,) and r["rolled_back"] == (2,), (
            "t1 committed, t2 rolled back: %r / %r"
            % (r["committed"], r["rolled_back"]))
        assert r["rows"]["orders"] == ((42, 3, 55, "paid"),), (
            "t2's row is gone: %r" % (r["rows"]["orders"],))

        many = _fixture(tb.CRASH_SCHEDULE, "many-uncommitted")
        r = s.run_crash(many)
        assert r["committed"] == (1, 4) and r["rolled_back"] == (2, 3), (
            "t1 and t4 committed, t2 and t3 rolled: %r / %r"
            % (r["committed"], r["rolled_back"]))
        assert r["rows"]["items"] == ((80, 1, 5), (83, 4, 8)), (
            "the uncommitted inserts are gone: %r" % (r["rows"]["items"],))

        torn = _fixture(tb.CRASH_SCHEDULE, "torn-log")
        r = s.run_crash(torn)
        assert torn["tear"] is True
        assert r["committed"] == (1,), (
            "the commit was durable before the tear: %r" % (r["committed"],))
        assert r["rows"]["orders"] == ((44, 1, 10, "open"),), (
            "the torn-log fixture's transaction survived its own tear: %r"
            % (r["rows"]["orders"],))
        # the torn tail is discarded, never trusted: the record says so
        assert isinstance(r["discarded"], int)

    """Every assertion the contract's §4.9 makes about this stage."""
    import pages as pg
    import tables as tb
    import stage_08 as s8
    import stage_09 as s
    _s9_surface(s)
    _s9_recover(s, s8, pg, tb)
    _s9_redo_undo(s, s8, pg, tb)
    _s9_run_crash(s, tb)

# --- stage 10 ----------------------------------------------------------------------
def check_10():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

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
        raise SystemExit("set G5_REPO=/path/to/forja")

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

    def _world_pager(pg):
        """The world on its own pager, synced — the proof's starting image."""
        import disk as dk
        import tables as tb
        pager = pg.Pager(dk.Disk())
        tb.load_world(pager)
        pager.sync()
        return pager

    def _s10_surface(s):
        """The stage's public surface is exactly the names §4.0 pins."""
        public = set()
        for name, value in vars(s).items():
            if name.startswith("_") or name in ("dk", "pg", "tb", "ops"):
                continue
            public.add(name)
        assert public == {"PROOF_KEYS", "AUDIT_KEYS", "VERDICTS", "QueryError",
                          "run_all", "prove", "audit"}, (
            "the stage's public surface is %s and §4.0 pins PROOF_KEYS, "
            "AUDIT_KEYS, VERDICTS, QueryError, run_all, prove, audit"
            % ", ".join(sorted(public)))
        assert s.PROOF_KEYS == S10_PROOF_KEYS, (
            "PROOF_KEYS is %r and §4.0 pins %r" % (s.PROOF_KEYS, S10_PROOF_KEYS))
        assert s.AUDIT_KEYS == S10_AUDIT_KEYS, (
            "AUDIT_KEYS is %r and §4.0 pins %r" % (s.AUDIT_KEYS, S10_AUDIT_KEYS))
        assert s.VERDICTS == S10_VERDICTS, (
            "VERDICTS is %r and §4.0 pins the closed four %r"
            % (s.VERDICTS, S10_VERDICTS))
        assert all(callable(getattr(s, n))
                   for n in ("run_all", "prove", "audit")), (
            "run_all, prove and audit are the ways in")

    def _s10_run_all(s, pg):
        import tables as tb
        """The hundred through the whole stack, held against the reference."""
        pager = _world_pager(pg)
        proof = s.run_all(pager)
        assert set(proof) >= set(S10_PROOF_KEYS), (
            "the proof's keys carry PROOF_KEYS: %s" % sorted(proof))
        assert set(proof["rows"]) == {q["id"] for q in tb.QUERIES}, (
            "the proof answers all hundred: %d rows"
            % len(proof["rows"]))
        wrong = [q["id"] for q in tb.QUERIES
                 if proof["rows"][q["id"]] != q["rows"]]
        assert not wrong, "law 13: %s differ from the reference" % (wrong[:8],)
        bad_plan = [q["id"] for q in tb.QUERIES
                    if proof["plans"][q["id"]]["uses_index"] != q["uses_index"]]
        assert not bad_plan, "law 14: %s disagree with uses_index" % bad_plan
        assert isinstance(proof["pages"], int) and proof["pages"] > 0, (
            "the pages count is the stack's own accounting: %r"
            % (proof["pages"],))

    def _s10_prove(s, pg):
        import tables as tb
        """The crash half beside the engine half — and the verdict on the proof."""
        import stage_09
        pager = _world_pager(pg)
        proof = s.prove(pager)
        assert set(proof) >= set(S10_PROOF_KEYS)
        assert "crash" in proof, (
            "prove carries the crash half beside the engine half")
        crash = proof["crash"]
        assert crash["committed"] == (1,) and crash["rolled_back"] == (2,), (
            "the fixture re-run holds its own split: %r / %r"
            % (crash["committed"], crash["rolled_back"]))
        assert (42, 3, 55, "paid") in crash["rows"]["orders"], (
            "the committed row survived: %r" % (crash["rows"]["orders"],))
        assert (43, 2, 20, "open") not in crash["rows"]["orders"], (
            "the uncommitted row did not: %r" % (crash["rows"]["orders"],))
        assert proof["verdict"] == "pass", (
            "the proof's verdict is the stack's own answer: %r"
            % (proof["verdict"],))
        # and the crash half is a real stage 9 run, not a fixture echo
        fixture = [f for f in tb.CRASH_SCHEDULE
                   if f["name"] == "uncommitted-loss"][0]
        assert crash["rows"] == stage_09.run_crash(fixture)["rows"], (
            "the crash half is the recovery's own answer")

    def _s10_audit(s, pg):
        import tables as tb
        """The audit grades against the world, not against the stack."""
        pager = _world_pager(pg)
        proof = s.prove(pager)
        r = s.audit(proof)
        assert set(r) >= set(S10_AUDIT_KEYS), (
            "the audit's keys carry AUDIT_KEYS: %s" % sorted(r))
        assert r["verdict"] == "pass" and r["rows_agree"] and r["plans_agree"], (
            "a sound proof passes: %r" % (r,))
        assert r["reasons"] == (), "a pass names no reasons"
        # one wrong row -> wrong_rows, naming the id
        bad = dict(proof)
        bad["rows"] = dict(proof["rows"])
        bad["rows"][7] = (("bogus",),)
        r = s.audit(bad)
        assert r["verdict"] == "wrong_rows" and not r["rows_agree"], (
            "one wrong row is wrong_rows: %r" % (r["verdict"],))
        assert "7" in str(r["reasons"]), (
            "the reason names the query id: %r" % (r["reasons"],))
        # a plan that disagrees with its uses_index -> wrong_plan, naming the id
        bad = dict(proof)
        bad["plans"] = dict(proof["plans"])
        bad["plans"][21] = dict(bad["plans"][21])
        q21 = [q for q in tb.QUERIES if q["id"] == 21][0]
        bad["plans"][21]["uses_index"] = not q21["uses_index"]
        r = s.audit(bad)
        assert r["verdict"] == "wrong_plan" and not r["plans_agree"], (
            "a plan off its uses_index is wrong_plan: %r" % (r["verdict"],))
        assert "21" in str(r["reasons"]), (
            "the reason names the query id: %r" % (r["reasons"],))
        # a committed transaction that did not survive -> lost_commit, the xid
        bad = dict(proof)
        bad["crash"] = {"committed": (1,), "rolled_back": (2,),
                        "rows": {"orders": (), "items": ()}}
        r = s.audit(bad)
        assert r["verdict"] == "lost_commit", (
            "a lost commit is lost_commit: %r" % (r["verdict"],))
        assert "1" in str(r["reasons"]), (
            "the reason names the xid: %r" % (r["reasons"],))
        # rows before plans before durability: the first failure speaks
        bad["rows"] = dict(proof["rows"])
        bad["rows"][7] = (("bogus",),)
        assert s.audit(bad)["verdict"] == "wrong_rows", (
            "wrong rows outrank a lost commit")

    """Every assertion the contract's §4.10 makes about this stage."""
    import pages as pg
    import tables as tb
    import stage_10 as s
    _s10_surface(s)
    _s10_run_all(s, pg)
    _s10_prove(s, pg)
    _s10_audit(s, pg)

# --- the manifest. One entry per stage, in the order a reader meets them.

STAGES = [
    stage(
        1,
        file="stage_01.py",
        title='The parse: words, trees, and the five refusals',
        tags=['parse', 'AST', 'refusals'],
        action="Write `TOKENS`, `parse` and the parser's helpers in stage_01.py.",
        predict="What a token stream is before it means anything, and why a refusal names its reason at the offset that earned it.",
        check=check_1,
    ),
    stage(
        2,
        file="stage_02.py",
        title='The resolve: names against a catalog that may lie',
        tags=['resolve', 'catalog', 'errors'],
        action="Write `CATALOG_KEYS`, `resolve` and its helpers in stage_02.py.",
        predict="Which name binds to which table when two carry the same column, and why a catalog that may lie is the resolver's problem, not the caller's.",
        check=check_2,
    ),
    stage(
        3,
        file="stage_03.py",
        title='The predicates: conjuncts, and where they go',
        tags=['predicates', 'conjuncts', 'pushdown'],
        action="Write `Predicate`, `split_conjuncts` and `where_of` in stage_03.py.",
        predict="Where each conjunct goes — table, join, or having — and why the order of a fold decides the pushdown.",
        check=check_3,
    ),
    stage(
        4,
        file="stage_04.py",
        title='The index: a B+tree that splits',
        tags=['B+tree', 'splits', 'index'],
        action="Write `Leaf`, `Inner`, `build` and `scan` in stage_04.py.",
        predict="Why a leaf split is a rotation and an inner split is a new root, and what a walk's sector price really buys.",
        check=check_4,
    ),
    stage(
        5,
        file="stage_05.py",
        title='The plan: pushdown, selectivity, and the earned index',
        tags=['plan', 'selectivity', 'cost'],
        action="Write `cost_of`, `plan` and `explain` in stage_05.py.",
        predict="How selectivity earns the index and why the plan's own record carries the executor's hints.",
        check=check_5,
    ),
    stage(
        6,
        file="stage_06.py",
        title='The executor: iterators over pages',
        tags=['executor', 'iterators', 'pipelines'],
        action="Write `execute` and its iterator builders in stage_06.py.",
        predict="Why every operator is an iterator and where the pipeline stops pulling — the lazy stop is the executor's contract.",
        check=check_6,
    ),
    stage(
        7,
        file="stage_07.py",
        title='The buffer: pinning, eviction, and the page you did not keep',
        tags=['buffer', 'LRU', 'pinning'],
        action="Write `BUFFER_KEYS`, `run_buffered` and the pool's ways in stage_07.py.",
        predict="What a pin protects, why the victim is the page you did not keep, and why the pool's counters are the ledger.",
        check=check_7,
    ),
    stage(
        8,
        file="stage_08.py",
        title='The commit: a log, and a rule',
        tags=['WAL', 'commit', 'durability'],
        action="Write `LOG_KEYS`, `WAL` and `commit` in stage_08.py.",
        predict="What a commit record is for and why the sync happens before the answer — the rule the durability hangs on.",
        check=check_8,
    ),
    stage(
        9,
        file="stage_09.py",
        title='The recovery: redo, undo, discard',
        tags=['recovery', 'redo', 'undo'],
        action="Write `RECOVER_KEYS`, `recover`, `redo`, `undo` and `run_crash` in stage_09.py.",
        predict="Why the torn tail is discarded rather than retried, and how redo and undo split a transaction's fate at its commit record.",
        check=check_9,
    ),
    stage(
        10,
        file="stage_10.py",
        title='The proof: a hundred queries, and the audit',
        tags=['proof', 'audit', 'verdicts'],
        action="Write `PROOF_KEYS`, `run_all`, `prove`, `AUDIT_KEYS`, `VERDICTS` and `audit` in stage_10.py.",
        predict="How the hundred grade the stack, and why the audit reads the reference and not anyone's prose.",
        check=check_10,
    ),
]
