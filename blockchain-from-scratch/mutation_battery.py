"""Mutation battery for blockchain-from-scratch.

Tests that every test actually catches bugs by introducing small
mutations (code faults) and verifying each is detected (KILLED).

A mutation that is NOT detected (MISSED) means the test suite
lacks coverage for that particular fault.

Usage:
    python3 mutation_battery.py
"""

import sys
import os
import importlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "solutions"))


class MutationResult:
    """Result of testing one mutation."""

    def __init__(self, description, killed, detail=""):
        self.description = description
        self.killed = killed
        self.detail = detail

    def __repr__(self):
        status = "KILLED" if self.killed else "MISSED"
        return f"{status}: {self.description}" + (f" — {self.detail}" if self.detail else "")


def run_check_fn(check_fn, stage_mod_name):
    """Run a check function against the solutions. Returns True if PASS."""
    try:
        check_fn()
        return True
    except AssertionError:
        return False
    except NotImplementedError:
        return False


# ---------------------------------------------------------------------------
# The check functions (extracted from course.py)
# ---------------------------------------------------------------------------

def _check_1():
    import ledger
    import stage_01 as s

    assert tuple(s.HEADER_KEYS) == ("height", "prev_hash", "tx_root", "tick", "target")
    assert s.GENESIS_HASH == ledger.GENESIS_HASH
    assert issubclass(s.BlockError, ledger.LedgerError)
    assert s.BlockError is not ledger.LedgerError

    h = s.spawn(0, ledger.GENESIS_HASH, "0" * 64, 0, ledger.MAX_TARGET)
    assert h["height"] == 0
    assert h["prev_hash"] == ledger.GENESIS_HASH
    assert h["tx_root"] == "0" * 64
    assert h["tick"] == 0
    assert h["target"] == ledger.MAX_TARGET

    seal_val = s.seal(h)
    assert len(seal_val) == 64
    assert all(c in "0123456789abcdef" for c in seal_val)

    s.link._registry[seal_val] = h
    h1 = s.link(seal_val, ["tx1", "tx2"], 1, ledger.MAX_TARGET)
    assert h1["height"] == 1
    assert h1["prev_hash"] == seal_val
    assert h1["tx_root"] == "0" * 64
    assert h1["tick"] == 1
    assert h1["target"] == ledger.MAX_TARGET

    assert s.seal(h) == seal_val

    h2 = s.spawn(0, ledger.GENESIS_HASH, "0" * 64, 1, ledger.MAX_TARGET)
    assert s.seal(h2) != seal_val, "seal must depend on tick, not just height"
    h3v = s.spawn(0, "00" * 32, "0" * 64, 0, ledger.MAX_TARGET)
    assert s.seal(h3v) != seal_val, "seal must depend on prev_hash"

    s.link._registry[seal_val] = h
    h1 = s.link(seal_val, ["tx1", "tx2"], 1, ledger.MAX_TARGET)
    assert h1["height"] == 1
    assert h1["prev_hash"] == seal_val
    seal1 = s.seal(h1)
    s.link._registry[seal1] = h1
    h2 = s.link(seal1, ["tx3"], 2, ledger.MAX_TARGET)
    assert h2["height"] == 2
    assert h2["prev_hash"] == seal1, "block 2 must link to block 1's seal"
    assert h2["tick"] == 2

    s.link._registry = {}
    g = s.spawn(0, ledger.GENESIS_HASH, "0" * 64, 0, ledger.MAX_TARGET)
    sg = s.seal(g)
    s.link._registry[sg] = g
    b1 = s.link(sg, ["x"], 1, ledger.MAX_TARGET)
    b2_seal = s.seal(b1)
    b2 = s.link(b2_seal, ["y"], 2, ledger.MAX_TARGET)
    assert b2["height"] == 2

    try:
        s.spawn(-1, ledger.GENESIS_HASH, "0" * 64, 0, ledger.MAX_TARGET)
        assert False, "should refuse negative height"
    except s.BlockError as e:
        assert "height" in str(e) or "zero" in str(e)

    try:
        s.spawn(0, "bad", "0" * 64, 0, ledger.MAX_TARGET)
        assert False, "should refuse bad prev_hash"
    except s.BlockError as e:
        assert "prev_hash" in str(e) or "64" in str(e) or "hex" in str(e)

    h2 = s.spawn(0, ledger.GENESIS_HASH, "0" * 64, 0, ledger.MAX_TARGET)
    assert s.seal(h2) == seal_val


def _check_2():
    import ledger
    import stage_02 as s

    assert tuple(s.MERKLE_KEYS) == ("tx_count", "leaf_count", "root", "depth", "leaves", "duplicates")
    assert issubclass(s.MerkleError, ledger.LedgerError)

    tx_ids = ("tx_a", "tx_b", "tx_c", "tx_d")
    leaf_list = s.leaves(tx_ids)
    assert len(leaf_list) == 4
    for i, tid in enumerate(tx_ids):
        expected = ledger.digest(tid)
        assert leaf_list[i] == expected, "leaf[%d] mismatch" % i

    mroot = s.root(tx_ids)
    assert len(mroot) == 64
    for leaf in leaf_list:
        assert mroot != leaf

    for tid in tx_ids:
        proof = s.proof(tx_ids, tid)
        assert s.confirm(tid, proof, mroot), "proof failed for %s" % tid

    bad_proof = s.proof(tx_ids, "tx_a")
    assert not s.confirm("tx_b", bad_proof, mroot)

    try:
        s.proof(tx_ids, "tx_not_here")
        assert False, "should refuse unknown tx"
    except s.MerkleError:
        pass

    tx_ids3 = ("tx_a", "tx_b", "tx_c")
    root3 = s.root(tx_ids3)
    assert root3 != s.root(("tx_a", "tx_b", "tx_c", "tx_d"))

    proof_a = s.proof(("tx_a", "tx_b", "tx_c"), "tx_a")
    current = ledger.digest("tx_a")
    for sibling, direction in proof_a:
        if direction == "left":
            combined = ledger.canonical(sibling) + ledger.canonical(current)
        else:
            combined = ledger.canonical(current) + ledger.canonical(sibling)
        current = ledger._hash_bytes(combined)
    assert current == root3, "proof walk did not reconstruct root"

    _pad_sha = lambda d: ledger.digest(d)
    _pad_hash = lambda a, b: ledger._hash_bytes(ledger.canonical(a) + ledger.canonical(b))
    pad_leaves = [_pad_sha(x) for x in ("pad_a", "pad_b", "pad_c")]
    pad_layer = list(pad_leaves)
    pad_layer.append("0" * 64)
    pad_layer = [_pad_hash(pad_layer[i], pad_layer[i + 1]) for i in range(0, 4, 2)]
    pad_layer.append("0" * 64)
    pad_layer = [_pad_hash(pad_layer[i], pad_layer[i + 1]) for i in range(0, 2, 2)]
    padded_root = pad_layer[0]

    pad_dupe_leaves = [_pad_sha(x) for x in ("pad_x", "pad_y", "pad_z")]
    pad_layer2 = list(pad_dupe_leaves)
    pad_layer2.append(pad_layer2[-1])
    pad_layer2 = [_pad_hash(pad_layer2[i], pad_layer2[i + 1]) for i in range(0, 4, 2)]
    pad_layer2.append(pad_layer2[-1])
    pad_layer2 = [_pad_hash(pad_layer2[i], pad_layer2[i + 1]) for i in range(0, 2, 2)]
    dupe_root = pad_layer2[0]

    actual = s.root(("pad_x", "pad_y", "pad_z"))
    assert actual == dupe_root, (
        "odd-count root %r should match duplicate (not pad-zeros %r)" % (actual, padded_root))

    try:
        s.root(())
        assert False, "should refuse empty"
    except s.MerkleError:
        pass

    mroot2 = s.root(tx_ids)
    assert mroot2 == mroot


def _check_3():
    import ledger
    import keys
    import stage_03 as s

    assert tuple(s.ADDR_KEYS) == ("address", "pub_hex")
    assert tuple(s.SIGN_KEYS) == ("R", "s", "tx_id", "signer")
    assert issubclass(s.BindingError, ledger.LedgerError)

    priv = keys.keygen(12345)
    pub = keys.pubkey(priv)
    addr = s._wallet(pub)
    expected_addr = keys.address(pub)
    assert addr == expected_addr

    tx = {"tx_id": "demo_tx", "inputs": [{"prev_tx_id": "gen", "prev_index": 0}],
          "outputs": [{"address": addr, "amount_cents": 100}]}
    signed = s.witness(tx, priv, pub)
    assert "signatures" in signed

    sig = signed["signatures"][addr]
    assert s.verify_input(signed, 0, pub, (sig["R"], sig["s"]))

    bad_tx = {"tx_id": "wrong_tx", "inputs": [{"prev_tx_id": "gen", "prev_index": 0}],
              "outputs": [{"address": addr, "amount_cents": 200}]}
    assert not s.verify_input(bad_tx, 0, pub, (sig["R"], sig["s"]))

    try:
        priv2 = keys.keygen(99999)
        pub2 = keys.pubkey(priv2)
        s.witness(tx, priv2, pub)
        assert False, "should refuse mismatched key pair"
    except s.BindingError:
        pass

    sig_data = signed["signatures"][addr]
    sig_tuple = (sig_data["R"], sig_data["s"])
    assert s.verify_input(signed, 0, pub, sig_tuple)


def _check_4():
    import ledger
    import stage_04 as s

    assert tuple(s.UTXO_KEYS) == ("tx_id", "index", "address", "amount_cents")
    assert issubclass(s.SetError, ledger.LedgerError)

    blocks = [{"header": {"height": 0}, "transactions": [
        {"tx_id": "gen0", "inputs": [], "outputs": [
            {"address": "alice", "amount_cents": 1000},
            {"address": "bob", "amount_cents": 500},
        ]},
    ]}]
    utxo = s.outpoints(blocks)
    assert len(utxo) == 2

    assert s.balance(utxo, "alice") == 1000
    assert s.balance(utxo, "bob") == 500
    assert s.balance(utxo, "nobody") == 0

    new_tx = {"tx_id": "spend1", "inputs": [{"prev_tx_id": "gen0", "prev_index": 0}],
              "outputs": [{"address": "alice", "amount_cents": 800}]}
    new_utxo = s.apply(utxo, new_tx)
    assert len(new_utxo) == 2

    try:
        bad_tx = {"tx_id": "bad", "inputs": [{"prev_tx_id": "gen0", "prev_index": 99}],
                  "outputs": [{"address": "alice", "amount_cents": 100}]}
        s.apply(utxo, bad_tx)
        assert False, "should refuse missing outpoint"
    except s.SetError as e:
        assert "not found" in str(e)

    try:
        owner_tx = {"tx_id": "owner_tx", "inputs": [{"prev_tx_id": "gen0", "prev_index": 0}],
                    "outputs": [{"address": "charlie", "amount_cents": 500}]}
        s.apply(utxo, owner_tx)
        assert False, "should refuse wrong owner"
    except s.SetError as e:
        assert "not owned" in str(e).lower() or "owner" in str(e).lower()


def _check_5():
    import ledger
    import stage_05 as s

    assert tuple(s.POOL_KEYS) == ("tx_count", "total_fee", "tx_ids")
    assert issubclass(s.PoolError, ledger.LedgerError)

    pool = []
    utxo = {("gen0", 0): ("alice", 1000)}

    tx1 = {"tx_id": "tx1", "inputs": [{"prev_tx_id": "gen0", "prev_index": 0}],
           "outputs": [{"address": "bob", "amount_cents": 900}]}
    assert s.admit(pool, tx1, utxo, {})
    assert len(pool) == 1

    tx2 = {"tx_id": "tx2", "inputs": [{"prev_tx_id": "gen0", "prev_index": 0}],
           "outputs": [{"address": "charlie", "amount_cents": 800}]}
    assert s.is_double_spend(pool, tx2), "tx2 double-spends tx1"
    assert not s.admit(pool, tx2, utxo, {}), "double-spend rejected"
    assert len(pool) == 1

    ranked = s.rank(pool)
    assert "tx1" in ranked

    zero_fee_tx = {"tx_id": "free_tx", "inputs": [{"prev_tx_id": "gen0", "prev_index": 0}],
                   "outputs": [{"address": "bob", "amount_cents": 1000}]}
    assert not s.admit(pool, zero_fee_tx, utxo, {}), "zero-fee tx must be refused"

    zero_tx2 = {"tx_id": "free2", "inputs": [{"prev_tx_id": "gen0", "prev_index": 0}],
                "outputs": [{"address": "bob", "amount_cents": 1000}]}
    assert not s.admit(pool, zero_tx2, utxo, {})


def _check_6():
    import ledger
    import stage_06 as s

    assert tuple(s.POW_KEYS) == ("digest_int", "target", "meets", "nonce")
    assert issubclass(s.PowError, ledger.LedgerError)

    assert s.meets(0, 100)
    assert s.meets(100, 100)
    assert not s.meets(101, 100)

    header = {"height": 0, "prev_hash": "0" * 64, "tx_root": "0" * 64,
              "tick": 0, "target": ledger.MAX_TARGET}
    nonce, new_header = s.mine(header, ledger.MAX_TARGET, 1000)
    assert s.meets(int(ledger.digest(new_header), 16), ledger.MAX_TARGET)

    try:
        s.mine(header, 1, 10)
        assert False, "should refuse budget exhausted"
    except s.PowError as e:
        assert "budget" in str(e).lower()

    old_target = 1000000
    new = s.retarget(old_target, 3)
    assert new >= old_target // 4, "should clamp to quarter"
    new2 = s.retarget(old_target, 1000000)
    assert new2 <= old_target * 4, "should clamp to quadruple"


def _check_7():
    import ledger
    import keys
    import stage_07 as s

    assert tuple(s.SLOT_KEYS) == ("slot_num", "proposer", "cumulative", "total_stake")
    assert issubclass(s.SlotError, ledger.LedgerError)

    stakes = [{"peer": "alpha", "stake": 50}, {"peer": "beta", "stake": 30},
              {"peer": "gamma", "stake": 20}]
    for slot in range(5):
        prop = s.proposer(slot, stakes)
        assert prop in ["alpha", "beta", "gamma"]

    try:
        s.proposer(0, [])
        assert False, "should refuse empty stakes"
    except s.SlotError:
        pass

    stakes3 = [{"peer": "a", "stake": 13}, {"peer": "b", "stake": 87}]
    prop_0 = s.proposer(0, stakes3)
    assert prop_0 == "b", "draw=13 with cum_a=13: must be b"

    priv = keys.keygen(54321)
    attn0 = s.witness("block_001", 0, priv)
    attn1 = s.witness("block_001", 1, priv)
    assert attn0["sig"] != attn1["sig"]

    stake_map = {"alpha": 50, "beta": 30, "gamma": 20}
    attn = {"block_id": "block_001", "slot": 0, "signer": "alpha", "sig": (1, 2)}
    total = s.summed(stake_map, [attn])
    assert total == 50


def _check_8():
    import ledger
    import stage_08 as s

    assert tuple(s.FORK_KEYS) == ("total_weight", "chain_length", "final_hash", "chosen")
    assert issubclass(s.ForkError, ledger.LedgerError)

    chain_a = [{"block_hash": "aaa", "height": 10}, {"block_hash": "bbb", "height": 11}]
    chain_b = [{"block_hash": "ccc", "height": 5}, {"block_hash": "ddd", "height": 6}]
    attestations = [{"block_id": "bbb", "signer": "alpha"}]
    assert s.honest_weight(chain_a, attestations) == 1
    assert s.honest_weight(chain_b, attestations) == 0

    view = {"attestations": attestations, "stakes": {"alpha": 50}}
    chosen = s.head([chain_a, chain_b], view)
    assert chosen == chain_a

    attestations2 = [{"block_id": "bbb", "signer": "alpha"},
                     {"block_id": "ddd", "signer": "beta"}]
    view2 = {"attestations": attestations2, "stakes": {"alpha": 50, "beta": 30}}
    chosen2 = s.head([chain_a, chain_b], view2)
    assert chosen2 == chain_a

    try:
        s.head([], view)
        assert False, "should refuse no candidates"
    except s.ForkError:
        pass

    assert s.verify_purity(lambda v: s.head([chain_a, chain_b], v), view)

    chain_low = [{"block_hash": "zzz", "height": 100}]
    chain_high = [{"block_hash": "aaa", "height": 1}]
    attestations_high = [{"block_id": "aaa", "signer": "alpha"}]
    view_high = {"attestations": attestations_high, "stakes": {"alpha": 50}}
    chosen_high = s.head([chain_low, chain_high], view_high)
    assert chosen_high == chain_high, "must return chain with highest weight"


def _check_9():
    import ledger
    import stage_09 as s

    assert tuple(s.NODE_KEYS) == ("name", "chain_length", "mempool_size", "utxo_count", "known_hashes")
    assert issubclass(s.NodeError, ledger.LedgerError)

    node = {"name": "test", "chain": [], "utxo": {}, "mempool_ids": set(),
            "messages_received": [], "messages_accepted": [], "messages_refused": []}

    tx = {"tx_id": "tx1", "inputs": [{"prev_tx_id": "gen0", "prev_index": 0}],
          "outputs": [{"address": "alice", "amount_cents": 900}]}
    node["utxo"][("gen0", 0)] = ("alice", 1000)
    ok = s.admit_tx(node, tx)
    assert ok is True

    block = {"header": {"prev_hash": ledger.GENESIS_HASH, "height": 1,
                        "tx_root": "0" * 64, "tick": 0, "target": ledger.MAX_TARGET,
                        "nonce": 0},
             "transactions": []}
    ok = s.consider_block(node, block)
    assert ok is True
    assert len(node.get("chain", [])) == 1

    bad_block = {"header": {"prev_hash": "bad" * 16, "height": 2}, "transactions": []}
    ok = s.consider_block(node, bad_block)
    assert ok is False

    audit_log = s.audit(node)
    assert audit_log["chain_length"] == 1
    assert audit_log["mempool_size"] == 1

    block_bad = {"header": {"prev_hash": ledger.GENESIS_HASH, "height": 2,
                            "tx_root": "0" * 64, "tick": 1,
                            "target": 10,
                            "nonce": 0},
                 "transactions": []}
    ok = s.consider_block(node, block_bad)
    assert ok is False, "block with PoW below target must be refused"

    tip = node.get("chain", [])[-1]["header"]["prev_hash"] if node.get("chain") else ledger.GENESIS_HASH
    block_good = {"header": {"prev_hash": tip, "height": 3, "tx_root": "0" * 64, "tick": 2,
                              "target": ledger.MAX_TARGET, "nonce": 0},
                  "transactions": []}
    ok2 = s.consider_block(node, block_good)
    assert ok2 is True, "block with valid PoW must be accepted"


def _check_10():
    import ledger
    import keys
    import net
    import stage_10 as s

    assert tuple(s.CONVERGE_KEYS) == ("all_nodes_same", "matches_key", "fork_lost", "node_count", "head")
    assert issubclass(s.ConvergeError, ledger.LedgerError)

    scenario = net.scenario(42)
    assert "delivery_log" in scenario
    assert "allocations" in scenario
    assert "transfers" in scenario
    assert "fork" in scenario

    result = s.converge(net, scenario)
    assert "all_nodes_same" in result
    assert "node_count" in result
    assert result["node_count"] == 5
    assert result["node_count"] == 5
    assert result.get("head") is not None

    nodes = [net.peer(name) for name in net.roster()]
    key = net.honest_answer_key(scenario)
    verification = s.verify_against_key(nodes, key)
    assert isinstance(verification, dict)
    for name in net.roster():
        assert name in verification

    audit_report = s.audit_convergence(nodes, key)
    assert isinstance(audit_report, list)
    assert len(audit_report) == 5


# ---------------------------------------------------------------------------
# Mutations
# ---------------------------------------------------------------------------

CHECK_FUNCS = {
    1: _check_1,
    2: _check_2,
    3: _check_3,
    4: _check_4,
    5: _check_5,
    6: _check_6,
    7: _check_7,
    8: _check_8,
    9: _check_9,
    10: _check_10,
}


def _inject_mutation(stage_num, mutation_fn):
    """Run a check with a mutation injected into the solutions stage module.

    mutation_fn(stage_module) — modifies the stage module in place,
    must be reverted by the caller (or we reload from scratch).
    """
    # We need to test against the solution files, so we reload the module fresh
    # each time to avoid cached state.
    result = []

    def make_check(stage_num, orig_check_fn, mutation_fn_inner):
        def check_with_mutation():
            # Clear cached modules
            for key in list(sys.modules.keys()):
                if key.startswith('stage_') or key.startswith('solutions.stage_'):
                    del sys.modules[key]

            # Import the stage module from solutions/
            stage_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                       'solutions', f'stage_{stage_num:02d}.py')

            # Read the original source
            with open(stage_path, 'r') as f:
                original_source = f.read()

            try:
                # Apply mutation
                mutated_source = mutation_fn_inner(original_source)

                # Write mutated version temporarily
                with open(stage_path, 'w') as f:
                    f.write(mutated_source)

                # Import fresh
                import importlib.util
                spec = importlib.util.spec_from_file_location(
                    f'stage_{stage_num:02d}', stage_path)
                stage_mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(stage_mod)

                # Run the check with this module
                return orig_check_fn(stage_mod)
            finally:
                # Restore original source
                with open(stage_path, 'w') as f:
                    f.write(original_source)

        return check_with_mutation

    return make_check(stage_num, CHECK_FUNCS[stage_num], mutation_fn)


# ---------------------------------------------------------------------------
# Mutations per stage
# ---------------------------------------------------------------------------

def run_mutation_battery():
    """Run all mutations and report results."""
    results = []

    # Helper to run a mutation test
    def test_mutation(stage_num, description, mutation_fn):
        check_fn = _inject_mutation(stage_num, mutation_fn)
        try:
            check_fn()
            # Check still passes → mutation MISSED
            results.append(MutationResult(description, False,
                                          "check still passes — mutation not caught"))
        except AssertionError:
            # Check fails → mutation KILLED
            results.append(MutationResult(description, True))
        except Exception as e:
            results.append(MutationResult(description, True,
                                          f"error: {type(e).__name__}: {e}"))

    # ---- Stage 1 mutations ----
    test_mutation(1, "spawn: skip height validation (accept negative height)",
                  lambda src: src.replace('if height <= 0:', '# HEIGHT CHECK REMOVED'))

    test_mutation(1, "spawn: skip prev_hash validation",
                  lambda src: src.replace('# validate prev_hash', '# prev_hash validation skipped'))

    test_mutation(1, "seal: return zero digest instead of computing hash",
                  lambda src: src.replace('return ledger.digest(header)', 'return "0" * 64'))

    test_mutation(1, "link: don't set prev_hash on new block",
                  lambda src: src.replace('header["prev_hash"] = prev_hash',
                                          '# prev_hash not set'))

    test_mutation(1, "link: don't self-register new block",
                  lambda src: src.replace('self._registry[seal_val] = header', ''))

    # ---- Stage 2 mutations ----
    test_mutation(2, "leaves: return empty list for non-empty input",
                  lambda src: src.replace('return [ledger.digest(tid) for tid in tx_ids]',
                                          'return []'))

    test_mutation(2, "root: don't duplicate last leaf for odd count",
                  lambda src: src.replace(
                      'if len(leaves) % 2:\n'
                      '    leaves.append(leaves[-1])',
                      '# odd-count deduplication REMOVED'))

    test_mutation(2, "confirm: always return True",
                  lambda src: src.replace('return current_digest == expected_root',
                                          'return True'))

    test_mutation(2, "proof: return proof with wrong direction",
                  lambda src: src.replace('"right"', '"wrong_direction"'))

    # ---- Stage 3 mutations ----
    test_mutation(3, "verify_input: ignore challenge (always verify)",
                  lambda src: src.replace(
                      'challenge = ledger.digest(unsigned_tx)',
                      'challenge = R'))  # use R as challenge to always pass

    test_mutation(3, "witness: use wrong tx_id in challenge",
                  lambda src: src.replace(
                      'tx["tx_id"]', 'tx.get("wrong_key", "bogus_tx_id")'))

    # ---- Stage 4 mutations ----
    test_mutation(4, "apply: don't remove spent outpoint from UTXO",
                  lambda src: src.replace(
                      'del utxo[inp["prev_tx_id"], inp["prev_index"]]',
                      '# spent outpoint not removed'))

    test_mutation(4, "balance: add instead of subtract amounts",
                  lambda src: src.replace(
                      'total += amount', 'total -= amount'))

    test_mutation(4, "outpoints: skip genesis block (height 0)",
                  lambda src: src.replace(
                      'for block in blocks:',
                      'for block in blocks:\n'
                      '    if block["header"].get("height", 0) == 0:\n'
                      '        continue'))

    # ---- Stage 5 mutations ----
    test_mutation(5, "is_double_spend: always return False",
                  lambda src: src.replace('return False', 'return True'))

    test_mutation(5, "admit: don't check for double spend",
                  lambda src: src.replace(
                      'if is_double_spend(pool, tx):',
                      '# double-spend check REMOVED'))

    test_mutation(5, "admit: accept zero-fee transactions",
                  lambda src: src.replace(
                      'fee = value_in - value_out',
                      'fee = 999'))  # always positive fee

    # ---- Stage 6 mutations ----
    test_mutation(6, "meets: use < instead of <= (off-by-one)",
                  lambda src: src.replace('return digest_int <= target',
                                          'return digest_int < target'))

    test_mutation(6, "mine: don't increment nonce",
                  lambda src: src.replace(
                      'nonce += 1',
                      '# nonce += 1  (always use nonce 0)'))

    test_mutation(6, "retarget: double the clamp factor",
                  lambda src: src.replace(
                      'max(1, old_target // 4)',
                      'max(1, old_target // 2)'))

    test_mutation(6, "retarget: cap instead of clamp (always return old_target)",
                  lambda src: src.replace(
                      'return max(1, old_target // 4)',
                      'return old_target'))

    # ---- Stage 7 mutations ----
    test_mutation(7, "proposer: use >= instead of > (off-by-one)",
                  lambda src: src.replace(
                      'cumulative > draw',
                      'cumulative >= draw'))

    test_mutation(7, "proposer: always return first peer",
                  lambda src: src.replace(
                      'for stake_entry in stakes:',
                      'return stakes[0]["peer"]'))

    test_mutation(7, "summed: return sum of all stakes regardless of block_id",
                  lambda src: src.replace(
                      'if attn["block_id"] == block_id:',
                      'return sum(stake_map.values())'))

    # ---- Stage 8 mutations ----
    test_mutation(8, "honest_weight: count all attestations (not just on chain)",
                  lambda src: src.replace(
                      'if att["block_id"] == block["block_hash"]:',
                      'if True:'))

    test_mutation(8, "head: return first chain instead of highest weight",
                  lambda src: src.replace(
                      'best_weight = weight\n'
                      'best_chain = chain',
                      '# best chain selection REMOVED'))

    test_mutation(8, "head: flip tie-breaking to highest hash (wrong)",
                  lambda src: src.replace(
                      'if final_hash < best_final_hash:',
                      'if final_hash > best_final_hash:'))

    # ---- Stage 9 mutations ----
    test_mutation(9, "consider_block: skip prev_hash check",
                  lambda src: src.replace(
                      'expected_prev = chain[-1]["header"]["prev_hash"]',
                      'expected_prev = "IGNORED"'))

    test_mutation(9, "consider_block: always accept blocks (skip all checks)",
                  lambda src: src.replace(
                      'if header.get("prev_hash") != expected_prev:',
                      'if False:'))

    test_mutation(9, "consider_block: skip PoW check",
                  lambda src: src.replace(
                      'if digest_int > target:',
                      'if False:'))

    test_mutation(9, "consider_block: use genesis for all blocks (no chain linking)",
                  lambda src: src.replace(
                      'expected_prev = chain[-1]["header"]["prev_hash"]',
                      'expected_prev = ledger.GENESIS_HASH'))

    test_mutation(9, "admit_tx: don't check fee",
                  lambda src: src.replace(
                      'if fee <= 0:',
                      '# fee check skipped'))

    # ---- Stage 10 mutations ----
    test_mutation(10, "converge: don't process delivery log",
                  lambda src: src.replace(
                      'for entry in delivery_log:',
                      'return {"all_nodes_same": True, "node_count": 0, "head": None}'))

    test_mutation(10, "converge: always report all_nodes_same=True",
                  lambda src: src.replace(
                      '"all_nodes_same": all_same or len(heads) <= 1',
                      '"all_nodes_same": True'))

    test_mutation(10, "converge: always report matches_key=True",
                  lambda src: src.replace(
                      '"matches_key": matches_key',
                      '"matches_key": True'))

    test_mutation(10, "converge: always report fork_lost=True",
                  lambda src: src.replace(
                      '"fork_lost": fork_lost',
                      '"fork_lost": True'))

    test_mutation(10, "converge: create only 4 nodes instead of 5",
                  lambda src: src.replace(
                      'nodes = [net.peer(name) for name in net.roster()]',
                      'nodes = [net.peer(net.roster()[i]) for i in range(4)]'))

    # ---- Print results ----
    print("=" * 70)
    print("BLOCKCHAIN FROM SCRATCH — MUTATION BATTERY")
    print("=" * 70)

    killed = [r for r in results if r.killed]
    missed = [r for r in results if not r.killed]

    print(f"\nKilled: {len(killed)}")
    for r in killed:
        print(f"  ✓ KILLED: {r.description}")

    print(f"\nMissed: {len(missed)}")
    for r in missed:
        print(f"  ✗ MISSED: {r.description}")
        print(f"           {r.detail}")

    print(f"\nTotal: {len(results)} | Killed: {len(killed)} | Missed: {len(missed)}")
    print("=" * 70)

    return len(missed) == 0


if __name__ == "__main__":
    success = run_mutation_battery()
    sys.exit(0 if success else 1)