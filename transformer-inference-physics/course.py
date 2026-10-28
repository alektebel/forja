"""Transformer Inference Physics — the cost model that predicts TTFT and ITL.

Ten graded stages over a world provided as data (`configs.py`, `devices.py`,
`trace.py`), the way the rest of this repository teaches a mechanism: the
world is data and holds the measured trace, a stage is a file you write, a
check is what happens to it, and the trace's own reference implementation is
the judge — because an inference cost model you can be exactly wrong about
has exactly one authority, and the model's prediction is graded by equality
with it, one nanosecond at a time.

What the course is about, in one line: *prefill and decode are two
different machines wearing one model, and the race between flops and bytes
is won in integers.*

    the parameters: what a config is
    the flops: the compute budget
    the bytes: the memory budget
    the roofline: the race's rules
    prefill: TTFT's model
    decode: ITL's model
    the KV cache: the third budget
    the crossover: where decode stops being memory-bound
    quantization: the weights' half of the trade
    the audit: the model meets the measurement

The house laws hold here (`.i2-dev/CONTRACT.md` §1): standard library
only, no `float` anywhere — nanoseconds, bytes, flops and per-mille are
ints the whole way —, every division `//` with the rounding order pinned
formula by formula, no `math`, no `random`, no clock, no thread, no
socket, and a stage's job is the physics, never the measurement: the
world's trace is data a stage reads and never edits.

What the course does **not** do is measure anything: the trace is the
offline stand-in for Nsight Systems, with the profiler's own probe tax
pinned at 1500 ns — the one number between a cost model's arithmetic and
a profile's answer. Where each formula meets real silicon (the memcpy in
`nvidia-smi dmon`, the GEMM in `nsys profile` over `hk.transform`,
the achieved fractions in a tensor-core benchmark) lives in the course's
README — the runbook is hardware's half of the bargain.

    python3 codecraft/cli.py run transformer-inference-physics
"""

from codecraft.api import stage

TITLE = "Transformer Inference Physics"
DESCRIPTION = ("A cost model that predicts TTFT and ITL from the config "
               "alone, judged by equality against a measured trace: ten "
               "stages that count a transformer's parameters, flops and "
               "bytes, put the two budgets on one roofline, price the "
               "prefill and decode phases distinctly, tabulate the KV "
               "cache's rent, find the batch where decode leaves the "
               "memory-bound regime, trade the weights against quantization "
               "while the cache refuses to shrink, and audit every "
               "prediction against the world's measurements — integers and "
               "nanoseconds the whole way, the probe tax the only gap.")

LEVEL = "advanced"
ORDER = 38


# --- stage 1 -----------------------------------------------------------------------
def check_1():
    import os
    import shutil
    import subprocess
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "transformer-inference-physics"

    STAGE = 1

    STUB_MESSAGE = "stage 1: implement validate()"

    def _repo(start=None):
        for candidate_start in (os.environ.get("I2_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "configs.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set I2_REPO=/path/to/forja")

    def _harness_env(root):
        """Copy the repo's course into `root` with solutions/ overlaid."""
        repo = _repo(HERE)
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__"))
        overlay = os.path.join(course, "solutions")
        if os.path.isdir(overlay):
            for name in os.listdir(overlay):
                if name.startswith("stage_") and name.endswith(".py"):
                    shutil.copy2(os.path.join(overlay, name),
                                 os.path.join(course, name))

    def _refuses(exc, what, call, names=()):
        """`call()` must raise `exc` naming every string in `names`."""
        try:
            call()
        except exc as problem:
            text = str(problem)
            missing = [w for w in tuple(names) if w not in text]
            if missing:
                raise AssertionError(
                    "%s: refusal %r does not name %s"
                    % (what, text, missing))
        else:
            raise AssertionError("%s: no refusal" % (what,))

    def _template_verdict():
        """The template must be the exit-2 refusal, with its own message."""
        repo = _repo(HERE)
        root = tempfile.mkdtemp(prefix="i2_check01_tpl_")
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__",
                                                      "solutions"))
        try:
            code = ("import sys; sys.path.insert(0, %r)\n"
                    "import configs, stage_01 as s1\n"
                    "try:\n"
                    "    s1.validate(configs.CONFIGS['TINY_MHA'])\n"
                    "except NotImplementedError as e:\n"
                    "    assert 'implement' in str(e), e\n"
                    "    print('not implemented yet')\n"
                    "    raise SystemExit(42)\n"
                    "raise SystemExit(7)\n" % (course,))
            proc = subprocess.run([sys.executable, "-c", code],
                                  capture_output=True, text=True, timeout=120)
            if proc.returncode == 42 and "not implemented yet" in proc.stdout:
                return 2, proc.stdout.strip()
            return 1, "template did not raise the stub: %s" % (proc.stderr,)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    ambient = next((p for p in sys.path
                    if os.path.isfile(os.path.join(p, "configs.py"))
                    and os.path.isfile(os.path.join(p, "stage_01.py"))),
                    None)
    if ambient is not None:
        root = None
        course = ambient
    else:
        root = tempfile.mkdtemp(prefix="i2_check01_env_")
        course = os.path.join(root, COURSE)
        _harness_env(root)
        sys.path.insert(0, course)
    try:
        import configs
        import stage_01 as s1

        problems = []
        facts = 0

        def fact(label, ok):
            nonlocal facts
            facts += 1
            if not ok:
                problems.append(label)
                print("  !! %s" % (label,))

        def must(label, ok):
            if not ok:
                raise AssertionError(label)

        # --- the world's pins, re-read
        must("Config fields",
             configs.Config._fields == ("name", "n_layers", "d_model",
                                        "n_heads", "n_kv_heads", "head_dim",
                                        "d_ff", "vocab"))
        must("config rows", configs.CONFIG_NAMES
             == ("TINY_MHA", "SEVEN_MHA", "SEVEN_GQA", "SEVEN_MQA",
                 "BIG_GQA"))
        must("TINY row", configs.CONFIGS["TINY_MHA"]
             == ("TINY_MHA", 6, 384, 6, 6, 64, 1536, 4096))
        must("SEVEN_MHA row", configs.CONFIGS["SEVEN_MHA"]
             == ("SEVEN_MHA", 32, 4096, 32, 32, 128, 11008, 32000))
        must("SEVEN_GQA row", configs.CONFIGS["SEVEN_GQA"]
             == ("SEVEN_GQA", 32, 4096, 32, 8, 128, 11008, 32000))
        must("SEVEN_MQA row", configs.CONFIGS["SEVEN_MQA"]
             == ("SEVEN_MQA", 32, 4096, 32, 1, 128, 11008, 32000))
        must("BIG row", configs.CONFIGS["BIG_GQA"]
             == ("BIG_GQA", 80, 8192, 64, 8, 128, 28672, 128000))
        must("DTYPE_BYTES has no int4",
             configs.DTYPE_BYTES == {"fp16": 2, "fp8": 1, "int8": 1})

        # --- the stub probe: an untouched template answers exit 2
        stub = 0
        try:
            s1.validate(configs.CONFIGS["TINY_MHA"])
        except NotImplementedError as error:
            must("stub message", STUB_MESSAGE in str(error))
            stub += 1
        if stub:
            print("check_01: stage 1: not implemented yet (%s)"
                  % (STUB_MESSAGE,))
            raise SystemExit(2)

        must("PhysError is a ValueError",
             issubclass(s1.PhysError, ValueError))
        must("PARAM_KEYS", s1.PARAM_KEYS
             == ("attention", "mlp", "embedding", "total"))

        # the synthetic config the world never ships, and the one whose
        # matrices are odd-sized: per-matrix int4 packing is only
        # observable at ODD_TIE
        fake = configs.Config("FAKE_MHA", 3, 256, 4, 2, 64, 1024, 8192)
        odd = configs.Config("ODD_TIE", 1, 385, 5, 1, 77, 1, 385)

        # --- validate: every world row and both synthetics pass
        for name in configs.CONFIG_NAMES:
            s1.validate(configs.CONFIGS[name])
        s1.validate(fake)
        s1.validate(odd)
        fact("validate returns None on a good config",
             s1.validate(configs.CONFIGS["TINY_MHA"]) is None)

        # --- the refusal laws, each named
        untiled = configs.Config("BADTILE", 2, 256, 5, 1, 64, 128, 128)
        _refuses(s1.PhysError, "untiled heads refused",
                 lambda: s1.validate(untiled),
                 names=("BADTILE", "5", "64", "256"))
        indivisible = configs.Config("BADGROUP", 2, 255, 5, 2, 51, 128, 128)
        _refuses(s1.PhysError, "indivisible groups refused",
                 lambda: s1.validate(indivisible),
                 names=("BADGROUP", "5", "2"))
        zero_layer = configs.Config("ZL", 0, 256, 4, 2, 64, 1024, 8192)
        _refuses(s1.PhysError, "zero layers refused",
                 lambda: s1.validate(zero_layer),
                 names=("ZL", "n_layers", "0"))
        zero_vocab = configs.Config("ZV", 1, 64, 1, 1, 64, 64, 0)
        _refuses(s1.PhysError, "zero vocab refused",
                 lambda: s1.validate(zero_vocab), names=("ZV", "vocab"))
        _refuses(s1.PhysError, "count_params refuses an invalid config",
                 lambda: s1.count_params(untiled), names=("BADTILE",))
        _refuses(s1.PhysError, "weight_bytes refuses an invalid config",
                 lambda: s1.weight_bytes(untiled, "fp16"),
                 names=("BADTILE",))
        _refuses(s1.PhysError, "int4 path refuses an invalid config",
                 lambda: s1.weight_bytes(untiled, "int4"),
                 names=("BADTILE",))

        # --- count_params: the hand-derived literals (§2), every row
        must("TINY params", s1.count_params(configs.CONFIGS["TINY_MHA"])
             == {"attention": 3538944, "mlp": 10616832,
                 "embedding": 1572864, "total": 15728640})
        must("SEVEN_MHA params",
             s1.count_params(configs.CONFIGS["SEVEN_MHA"])
             == {"attention": 2147483648, "mlp": 4328521728,
                 "embedding": 131072000, "total": 6607077376})
        fact("SEVEN_GQA params",
             s1.count_params(configs.CONFIGS["SEVEN_GQA"])
             == {"attention": 1342177280, "mlp": 4328521728,
                 "embedding": 131072000, "total": 5801771008})
        fact("SEVEN_MQA params",
             s1.count_params(configs.CONFIGS["SEVEN_MQA"])
             == {"attention": 1107296256, "mlp": 4328521728,
                 "embedding": 131072000, "total": 5566889984})
        fact("BIG params", s1.count_params(configs.CONFIGS["BIG_GQA"])
             == {"attention": 12079595520, "mlp": 56371445760,
                 "embedding": 1048576000, "total": 69499617280})
        fact("FAKE params", s1.count_params(fake)
             == {"attention": 589824, "mlp": 2359296,
                 "embedding": 2097152, "total": 5046272})
        fact("ODD params", s1.count_params(odd)
             == {"attention": 355740, "mlp": 1155,
                 "embedding": 148225, "total": 505120})

        p = s1.count_params(configs.CONFIGS["SEVEN_GQA"])
        fact("total is the three summed",
             p["total"] == p["attention"] + p["mlp"] + p["embedding"])
        fact("GQA attention is MHA minus the KV shrink",
             p["attention"] + 32 * 4096 * (2 * 24 * 128)
             == s1.count_params(configs.CONFIGS["SEVEN_MHA"])["attention"])
        fact("keys are exactly PARAM_KEYS",
             tuple(s1.count_params(fake)) == s1.PARAM_KEYS)
        fact("deterministic",
             s1.count_params(odd) == s1.count_params(odd))

        # --- weight_bytes: the dtype rules (§2), literal by literal
        must("TINY fp16", s1.weight_bytes(configs.CONFIGS["TINY_MHA"], "fp16")
             == 31457280)
        fact("TINY fp8", s1.weight_bytes(configs.CONFIGS["TINY_MHA"], "fp8")
             == 15728640)
        fact("TINY int8", s1.weight_bytes(configs.CONFIGS["TINY_MHA"], "int8")
             == 15728640)
        must("SEVEN_GQA fp16",
             s1.weight_bytes(configs.CONFIGS["SEVEN_GQA"], "fp16")
             == 11603542016)
        fact("SEVEN_GQA int8",
             s1.weight_bytes(configs.CONFIGS["SEVEN_GQA"], "int8")
             == 5801771008)
        fact("BIG int8", s1.weight_bytes(configs.CONFIGS["BIG_GQA"], "int8")
             == 69499617280)
        must("fp8 and int8 share the row",
             s1.weight_bytes(fake, "fp8") == s1.weight_bytes(fake, "int8")
             == 5046272)

        # --- int4: PER MATRIX, never one shot. ODD_TIE is the witness:
        # per-matrix = 103758 + 74113 + 578 + 74113 = 252562, while
        # (total + 1) // 2 would answer 252560 — two bytes and a law apart.
        fact("FAKE int4", s1.weight_bytes(fake, "int4") == 2523136)
        must("ODD int4 packs per matrix",
             s1.weight_bytes(odd, "int4") == 252562)
        fact("ODD is not the one-shot pack",
             s1.weight_bytes(odd, "int4") != (s1.count_params(odd)["total"]
                                              + 1) // 2)
        fact("SEVEN_GQA int4",
             s1.weight_bytes(configs.CONFIGS["SEVEN_GQA"], "int4")
             == 2900885504)
        fact("TINY int4", s1.weight_bytes(configs.CONFIGS["TINY_MHA"], "int4")
             == 7864320)
        fact("BIG int4", s1.weight_bytes(configs.CONFIGS["BIG_GQA"], "int4")
             == 34749808640)

        # --- the dtype refusal names the dtype and the table's rows
        _refuses(s1.PhysError, "fp32 refused",
                 lambda: s1.weight_bytes(fake, "fp32"),
                 names=("fp32", "fp16", "fp8", "int8"))
        _refuses(s1.PhysError, "fp16 capitalised refused",
                 lambda: s1.weight_bytes(fake, "FP16"), names=("FP16",))
        _refuses(s1.PhysError, "empty dtype refused",
                 lambda: s1.weight_bytes(fake, ""), names=("",))

        if problems:
            raise AssertionError("%d facts failed" % (len(problems),))
        print("check_01: PASS (%d facts)" % (facts,))
        return 0
    finally:
        if root:
            sys.path[:] = [p for p in sys.path if p != course]
            shutil.rmtree(root, ignore_errors=True)

# --- stage 2 -----------------------------------------------------------------------
def check_2():
    import os
    import shutil
    import subprocess
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "transformer-inference-physics"

    STAGE = 2

    STUB_MESSAGE = "stage 2: implement flops_token()"

    def _repo(start=None):
        for candidate_start in (os.environ.get("I2_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "configs.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set I2_REPO=/path/to/forja")

    def _harness_env(root):
        """Copy the repo's course into `root` with solutions/ overlaid."""
        repo = _repo(HERE)
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__"))
        overlay = os.path.join(course, "solutions")
        if os.path.isdir(overlay):
            for name in os.listdir(overlay):
                if name.startswith("stage_") and name.endswith(".py"):
                    shutil.copy2(os.path.join(overlay, name),
                                 os.path.join(course, name))

    def _refuses(exc, what, call, names=()):
        """`call()` must raise `exc` naming every string in `names`."""
        try:
            call()
        except exc as problem:
            text = str(problem)
            missing = [w for w in tuple(names) if w not in text]
            if missing:
                raise AssertionError(
                    "%s: refusal %r does not name %s"
                    % (what, text, missing))
        else:
            raise AssertionError("%s: no refusal" % (what,))

    def _template_verdict():
        """The template must be the exit-2 refusal, with its own message."""
        repo = _repo(HERE)
        root = tempfile.mkdtemp(prefix="i2_check02_tpl_")
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__",
                                                      "solutions"))
        try:
            code = ("import sys; sys.path.insert(0, %r)\n"
                    "import configs, stage_02 as s2\n"
                    "try:\n"
                    "    s2.flops_token(configs.CONFIGS['TINY_MHA'], 1)\n"
                    "except NotImplementedError as e:\n"
                    "    assert 'implement' in str(e), e\n"
                    "    print('not implemented yet')\n"
                    "    raise SystemExit(42)\n"
                    "raise SystemExit(7)\n" % (course,))
            proc = subprocess.run([sys.executable, "-c", code],
                                  capture_output=True, text=True, timeout=120)
            if proc.returncode == 42 and "not implemented yet" in proc.stdout:
                return 2, proc.stdout.strip()
            return 1, "template did not raise the stub: %s" % (proc.stderr,)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    ambient = next((p for p in sys.path
                    if os.path.isfile(os.path.join(p, "configs.py"))
                    and os.path.isfile(os.path.join(p, "stage_02.py"))),
                    None)
    if ambient is not None:
        root = None
        course = ambient
    else:
        root = tempfile.mkdtemp(prefix="i2_check02_env_")
        course = os.path.join(root, COURSE)
        _harness_env(root)
        sys.path.insert(0, course)
    try:
        import configs
        import stage_01 as s1
        import stage_02 as s2

        problems = []
        facts = 0

        def fact(label, ok):
            nonlocal facts
            facts += 1
            if not ok:
                problems.append(label)
                print("  !! %s" % (label,))

        def must(label, ok):
            if not ok:
                raise AssertionError(label)

        # --- the world's pins, re-read
        must("config rows", configs.CONFIG_NAMES
             == ("TINY_MHA", "SEVEN_MHA", "SEVEN_GQA", "SEVEN_MQA",
                 "BIG_GQA"))

        tiny = configs.CONFIGS["TINY_MHA"]
        stub = 0
        try:
            s2.flops_token(tiny, 1)
        except NotImplementedError as error:
            must("stub message", STUB_MESSAGE in str(error))
            stub += 1
        if stub:
            print("check_02: stage 2: not implemented yet (%s)"
                  % (STUB_MESSAGE,))
            raise SystemExit(2)

        must("FLOP_KEYS", s2.FLOP_KEYS
             == ("weights", "attention", "head", "total"))

        fake = configs.Config("FAKE_MHA", 3, 256, 4, 2, 64, 1024, 8192)
        # FAKE by hand (§2): attention params 589824, mlp 2359296
        # weights = 2 * (589824 + 2359296)            = 5898240
        # ctx=100 attention = 4*100*4*64*3            = 307200
        # head = 2*8192*256                           = 4194304
        # total = 5898240 + 307200 + 4194304          = 10399744
        must("FAKE token at ctx=100",
             s2.flops_token(fake, 100)
             == {"weights": 5898240, "attention": 307200,
                 "head": 4194304, "total": 10399744})
        # prefill FAKE p=10 batch=2: fuel 20
        # weights 5898240*20 = 117964800; attention 4*10*10*4*64*3*2 = 614400
        # head 4194304*2 = 8388608; total 126967808
        fact("FAKE prefill p=10 b=2",
             s2.flops_prefill(fake, 10, 2)
             == {"weights": 117964800, "attention": 614400,
                 "head": 8388608, "total": 126967808})

        # --- the world rows, literal by literal (§2)
        # TINY ctx=1: weights 2*(3538944+10616832)=28311552,
        # attention 4*1*6*64*6=9216, head 2*4096*384=3145728
        must("TINY token ctx=1",
             s2.flops_token(tiny, 1)
             == {"weights": 28311552, "attention": 9216,
                 "head": 3145728, "total": 31466496})
        must("TINY token ctx=1024",
             s2.flops_token(tiny, 1024)
             == {"weights": 28311552, "attention": 9437184,
                 "head": 3145728, "total": 40894464})
        # SEVEN_GQA ctx=4096: weights 2*(1342177280+4328521728)
        # = 11341398016; attention 4*4096*32*128*32 = 2147483648;
        # head 2*32000*4096 = 262144000
        fact("SEVEN_GQA token ctx=4096",
             s2.flops_token(configs.CONFIGS["SEVEN_GQA"], 4096)
             == {"weights": 11341398016, "attention": 2147483648,
                 "head": 262144000, "total": 13751025664})
        fact("keys are exactly FLOP_KEYS",
             tuple(s2.flops_token(fake, 7)) == s2.FLOP_KEYS)

        # GQA is invisible in the flops: H=32 in every seven-billion row
        fact("GQA attention equals MHA attention (H not hk)",
             s2.flops_token(configs.CONFIGS["SEVEN_GQA"], 1024)["attention"]
             == s2.flops_token(configs.CONFIGS["SEVEN_MHA"], 1024)
                ["attention"])
        fact("MQA too",
             s2.flops_token(configs.CONFIGS["SEVEN_MQA"], 1024)["attention"]
             == s2.flops_token(configs.CONFIGS["SEVEN_MHA"], 1024)
                ["attention"])
        # the weights line does shrink with the KV heads, though: the qkv
        # group is 32 * 4096 * 2 * (32 - 8) * 128 params narrower than MHA
        fact("GQA weights are MHA's minus twice the qkv shrink",
             s2.flops_token(configs.CONFIGS["SEVEN_GQA"], 1)["weights"]
             == s2.flops_token(configs.CONFIGS["SEVEN_MHA"], 1)["weights"]
             - 2 * (32 * 4096 * 2 * 24 * 128))

        # the embedding is a lookup, not a matmul: weights excludes it
        params = s1.count_params(tiny)
        fact("weights line is the stage-1 matmul params doubled",
             s2.flops_token(tiny, 1)["weights"]
             == 2 * (params["attention"] + params["mlp"]))
        fact("and never 2 * total",
             s2.flops_token(tiny, 1)["weights"]
             != 2 * params["total"])

        # --- prefill (§2): weights * prompt * batch, quadratic attention,
        # head once per sequence
        # TINY p=1024 b=1: weights 28311552*1024 = 28991029248;
        # attention 4*1024*1024*6*64*6 = 9663676416; head 3145728
        must("TINY prefill 1024 x 1",
             s2.flops_prefill(tiny, 1024, 1)
             == {"weights": 28991029248, "attention": 9663676416,
                 "head": 3145728, "total": 38657851392})
        fact("TINY prefill 1024 x 8",
             s2.flops_prefill(tiny, 1024, 8)
             == {"weights": 231928233984, "attention": 77309411328,
                 "head": 25165824, "total": 309262811136})
        # the quadratic law: doubling the prompt quadruples attention
        a1 = s2.flops_prefill(fake, 10, 1)["attention"]
        a2 = s2.flops_prefill(fake, 20, 1)["attention"]
        fact("attention is quadratic in the prompt", a2 == 4 * a1)
        fact("weights are linear in the prompt",
             s2.flops_prefill(fake, 20, 1)["weights"]
             == 2 * s2.flops_prefill(fake, 10, 1)["weights"])
        fact("head runs once per sequence",
             s2.flops_prefill(fake, 100, 3)["head"]
             == 3 * s2.flops_prefill(fake, 1, 1)["head"])

        # --- refusals: the boundary of one, named
        _refuses(s1.PhysError, "ctx=0 refused",
                 lambda: s2.flops_token(tiny, 0), names=("0",))
        _refuses(s1.PhysError, "ctx=-5 refused",
                 lambda: s2.flops_token(tiny, -5), names=("-5",))
        _refuses(s1.PhysError, "prompt_len=0 refused",
                 lambda: s2.flops_prefill(tiny, 0, 1),
                 names=("prompt_len", "0"))
        _refuses(s1.PhysError, "batch=0 refused",
                 lambda: s2.flops_prefill(tiny, 10, 0), names=("batch", "0"))
        untiled = configs.Config("BADTILE", 2, 256, 5, 1, 64, 128, 128)
        _refuses(s1.PhysError, "invalid config refused by name",
                 lambda: s2.flops_token(untiled, 1), names=("BADTILE",))
        _refuses(s1.PhysError, "invalid config refused in prefill",
                 lambda: s2.flops_prefill(untiled, 1, 1), names=("BADTILE",))

        if problems:
            raise AssertionError("%d facts failed" % (len(problems),))
        print("check_02: PASS (%d facts)" % (facts,))
        return 0
    finally:
        if root:
            sys.path[:] = [p for p in sys.path if p != course]
            shutil.rmtree(root, ignore_errors=True)

# --- stage 3 -----------------------------------------------------------------------
def check_3():
    import os
    import shutil
    import subprocess
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "transformer-inference-physics"

    STAGE = 3

    STUB_MESSAGE = "stage 3: implement kv_bytes_per_token()"

    def _repo(start=None):
        for candidate_start in (os.environ.get("I2_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "configs.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set I2_REPO=/path/to/forja")

    def _harness_env(root):
        """Copy the repo's course into `root` with solutions/ overlaid."""
        repo = _repo(HERE)
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__"))
        overlay = os.path.join(course, "solutions")
        if os.path.isdir(overlay):
            for name in os.listdir(overlay):
                if name.startswith("stage_") and name.endswith(".py"):
                    shutil.copy2(os.path.join(overlay, name),
                                 os.path.join(course, name))

    def _refuses(exc, what, call, names=()):
        """`call()` must raise `exc` naming every string in `names`."""
        try:
            call()
        except exc as problem:
            text = str(problem)
            missing = [w for w in tuple(names) if w not in text]
            if missing:
                raise AssertionError(
                    "%s: refusal %r does not name %s"
                    % (what, text, missing))
        else:
            raise AssertionError("%s: no refusal" % (what,))

    def _template_verdict():
        """The template must be the exit-2 refusal, with its own message."""
        repo = _repo(HERE)
        root = tempfile.mkdtemp(prefix="i2_check03_tpl_")
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__",
                                                      "solutions"))
        try:
            code = ("import sys; sys.path.insert(0, %r)\n"
                    "import configs, stage_03 as s3\n"
                    "try:\n"
                    "    s3.kv_bytes_per_token(configs.CONFIGS['TINY_MHA'])\n"
                    "except NotImplementedError as e:\n"
                    "    assert 'implement' in str(e), e\n"
                    "    print('not implemented yet')\n"
                    "    raise SystemExit(42)\n"
                    "raise SystemExit(7)\n" % (course,))
            proc = subprocess.run([sys.executable, "-c", code],
                                  capture_output=True, text=True, timeout=120)
            if proc.returncode == 42 and "not implemented yet" in proc.stdout:
                return 2, proc.stdout.strip()
            return 1, "template did not raise the stub: %s" % (proc.stderr,)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    ambient = next((p for p in sys.path
                    if os.path.isfile(os.path.join(p, "configs.py"))
                    and os.path.isfile(os.path.join(p, "stage_03.py"))),
                    None)
    if ambient is not None:
        root = None
        course = ambient
    else:
        root = tempfile.mkdtemp(prefix="i2_check03_env_")
        course = os.path.join(root, COURSE)
        _harness_env(root)
        sys.path.insert(0, course)
    try:
        import configs
        import stage_01 as s1
        import stage_02 as s2
        import stage_03 as s3

        problems = []
        facts = 0

        def fact(label, ok):
            nonlocal facts
            facts += 1
            if not ok:
                problems.append(label)
                print("  !! %s" % (label,))

        def must(label, ok):
            if not ok:
                raise AssertionError(label)

        tiny = configs.CONFIGS["TINY_MHA"]
        stub = 0
        try:
            s3.kv_bytes_per_token(tiny)
        except NotImplementedError as error:
            must("stub message", STUB_MESSAGE in str(error))
            stub += 1
        if stub:
            print("check_03: stage 3: not implemented yet (%s)"
                  % (STUB_MESSAGE,))
            raise SystemExit(2)

        must("BYTES_KEYS", s3.BYTES_KEYS == ("weights", "kv", "total"))

        fake = configs.Config("FAKE_MHA", 3, 256, 4, 2, 64, 1024, 8192)
        # FAKE by hand (§2): kv/token = 4*2*64*3 = 1536
        must("FAKE rent per token", s3.kv_bytes_per_token(fake) == 1536)
        # the world rows: 4*hk*h_d*L
        must("TINY rent", s3.kv_bytes_per_token(tiny) == 4 * 6 * 64 * 6)
        fact("SEVEN_MHA rent",
             s3.kv_bytes_per_token(configs.CONFIGS["SEVEN_MHA"]) == 524288)
        fact("SEVEN_GQA rent",
             s3.kv_bytes_per_token(configs.CONFIGS["SEVEN_GQA"]) == 131072)
        fact("SEVEN_MQA rent",
             s3.kv_bytes_per_token(configs.CONFIGS["SEVEN_MQA"]) == 16384)
        fact("BIG_GQA rent",
             s3.kv_bytes_per_token(configs.CONFIGS["BIG_GQA"]) == 327680)
        # the GQA law: rent follows hk, not H
        fact("GQA rents a quarter of MHA (hk 8 vs 32)",
             4 * s3.kv_bytes_per_token(configs.CONFIGS["SEVEN_GQA"])
             == s3.kv_bytes_per_token(configs.CONFIGS["SEVEN_MHA"]))
        # and the flops did NOT move (stage 2's mirror law)
        f = s2.flops_token(configs.CONFIGS["SEVEN_GQA"], 1024)
        g = s3.kv_bytes_per_token(configs.CONFIGS["SEVEN_GQA"])
        fact("GQA keeps MHA's attention flops while its rent shrinks",
             f["attention"] == 4 * 1024 * 32 * 128 * 32 and g == 131072)

        # --- kv_total
        must("FAKE kv_total at 1000", s3.kv_total(fake, 1000) == 1536000)
        fact("TINY kv_total 4096", s3.kv_total(tiny, 4096) == 37748736)
        fact("TINY kv_total 131072", s3.kv_total(tiny, 131072) == 1207959552)
        _refuses(s1.PhysError, "kv_total refuses ctx=0",
                 lambda: s3.kv_total(tiny, 0), names=("0",))
        _refuses(s1.PhysError, "kv_total refuses ctx=-1",
                 lambda: s3.kv_total(tiny, -1), names=("-1",))

        # --- bytes_decode (§2): weights once, cache read + store per
        # sequence
        # FAKE ctx=2 batch=3 fp16: weights 5046272*2 = 10092544;
        # kv = 1536*2*3 + 1536*3 = 9216 + 4608 = 13824
        must("FAKE bytes_decode ctx2 b3 fp16",
             s3.bytes_decode(fake, 2, 3, "fp16")
             == {"weights": 10092544, "kv": 13824, "total": 10106368})
        # TINY ctx=1024 b=8 int8: weights 15728640; kv = 9216*1024*8
        # + 9216*8 = 75497472 + 73728 = 75571200
        fact("TINY bytes_decode ctx1024 b8 int8",
             s3.bytes_decode(tiny, 1024, 8, "int8")
             == {"weights": 15728640, "kv": 75571200,
                 "total": 91299840})
        # int4: weights pack per matrix (2523136 for FAKE), kv fp16 anyway
        fact("FAKE bytes_decode int4 keeps fp16 kv",
             s3.bytes_decode(fake, 2, 3, "int4")
             == {"weights": 2523136, "kv": 13824, "total": 2536960})
        # the store law: batch=1 still pays one token's rent
        fact("the store is billed at batch 1",
             s3.bytes_decode(tiny, 1, 1, "fp16")["kv"] == 9216 + 9216)
        bd = s3.bytes_decode(fake, 5, 7, "fp16")
        fact("total sums", bd["total"] == bd["weights"] + bd["kv"])
        fact("keys are exactly BYTES_KEYS",
             tuple(s3.bytes_decode(fake, 5, 1, "fp16")) == s3.BYTES_KEYS)

        # --- bytes_prefill (§2): the stores only, no read
        # FAKE p=10 b=2: weights 10092544; kv = 1536*10*2 = 30720
        must("FAKE bytes_prefill p10 b2",
             s3.bytes_prefill(fake, 10, 2, "fp16")
             == {"weights": 10092544, "kv": 30720, "total": 10123264})
        fact("prefill stores exactly the cache that decode will read",
             s3.bytes_prefill(tiny, 1024, 1, "fp16")["kv"]
             == s3.kv_total(tiny, 1024))

        # --- refusals at the boundary of one
        _refuses(s1.PhysError, "bytes_decode ctx=0 refused",
                 lambda: s3.bytes_decode(tiny, 0, 1, "fp16"),
                 names=("ctx", "0"))
        _refuses(s1.PhysError, "bytes_decode batch=0 refused",
                 lambda: s3.bytes_decode(tiny, 5, 0, "fp16"),
                 names=("batch", "0"))
        _refuses(s1.PhysError, "bytes_prefill prompt_len=0 refused",
                 lambda: s3.bytes_prefill(tiny, 0, 1, "fp16"),
                 names=("prompt_len", "0"))
        _refuses(s1.PhysError, "bytes_prefill batch=0 refused",
                 lambda: s3.bytes_prefill(tiny, 8, 0, "fp16"),
                 names=("batch", "0"))
        untiled = configs.Config("BADTILE", 2, 256, 5, 1, 64, 128, 128)
        _refuses(s1.PhysError, "bytes_decode refuses invalid config",
                 lambda: s3.bytes_decode(untiled, 5, 1, "fp16"),
                 names=("BADTILE",))
        _refuses(s1.PhysError, "bad dtype reaches stage 1's refusal",
                 lambda: s3.bytes_decode(tiny, 5, 1, "fp32"),
                 names=("fp32",))

        # --- arithmetic_intensity: flops per kilobyte, floored once
        must("1000 flops over 4 bytes",
             s3.arithmetic_intensity(1000, 4) == 250000)
        fact("the floor is real: 7 flops 2 bytes = 3500",
             s3.arithmetic_intensity(7, 2) == 3500)
        fact("TINY qkv op intensity is exactly 1000",
             s3.arithmetic_intensity(2 * 442368, 884736) == 1000)
        _refuses(s1.PhysError, "intensity over 0 bytes refused",
                 lambda: s3.arithmetic_intensity(10, 0), names=("0",))
        _refuses(s1.PhysError, "intensity over negative bytes refused",
                 lambda: s3.arithmetic_intensity(10, -4), names=("-4",))

        if problems:
            raise AssertionError("%d facts failed" % (len(problems),))
        print("check_03: PASS (%d facts)" % (facts,))
        return 0
    finally:
        if root:
            sys.path[:] = [p for p in sys.path if p != course]
            shutil.rmtree(root, ignore_errors=True)

# --- stage 4 -----------------------------------------------------------------------
def check_4():
    import os
    import shutil
    import subprocess
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "transformer-inference-physics"

    STAGE = 4

    STUB_MESSAGE = "stage 4: implement op_time()"

    def _repo(start=None):
        for candidate_start in (os.environ.get("I2_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "configs.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set I2_REPO=/path/to/forja")

    def _harness_env(root):
        """Copy the repo's course into `root` with solutions/ overlaid."""
        repo = _repo(HERE)
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__"))
        overlay = os.path.join(course, "solutions")
        if os.path.isdir(overlay):
            for name in os.listdir(overlay):
                if name.startswith("stage_") and name.endswith(".py"):
                    shutil.copy2(os.path.join(overlay, name),
                                 os.path.join(course, name))

    def _refuses(exc, what, call, names=()):
        """`call()` must raise `exc` naming every string in `names`."""
        try:
            call()
        except exc as problem:
            text = str(problem)
            missing = [w for w in tuple(names) if w not in text]
            if missing:
                raise AssertionError(
                    "%s: refusal %r does not name %s"
                    % (what, text, missing))
        else:
            raise AssertionError("%s: no refusal" % (what,))

    def _template_verdict():
        """The template must be the exit-2 refusal, with its own message."""
        repo = _repo(HERE)
        root = tempfile.mkdtemp(prefix="i2_check04_tpl_")
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__",
                                                      "solutions"))
        try:
            code = ("import sys; sys.path.insert(0, %r)\n"
                    "import devices, stage_04 as s4\n"
                    "try:\n"
                    "    s4.op_time(10, 10, devices.DEVICES['D_CLASS'], 'fp16')\n"
                    "except NotImplementedError as e:\n"
                    "    assert 'implement' in str(e), e\n"
                    "    print('not implemented yet')\n"
                    "    raise SystemExit(42)\n"
                    "raise SystemExit(7)\n" % (course,))
            proc = subprocess.run([sys.executable, "-c", code],
                                  capture_output=True, text=True, timeout=120)
            if proc.returncode == 42 and "not implemented yet" in proc.stdout:
                return 2, proc.stdout.strip()
            return 1, "template did not raise the stub: %s" % (proc.stderr,)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    ambient = next((p for p in sys.path
                    if os.path.isfile(os.path.join(p, "configs.py"))
                    and os.path.isfile(os.path.join(p, "stage_04.py"))),
                    None)
    if ambient is not None:
        root = None
        course = ambient
    else:
        root = tempfile.mkdtemp(prefix="i2_check04_env_")
        course = os.path.join(root, COURSE)
        _harness_env(root)
        sys.path.insert(0, course)
    try:
        import configs
        import devices
        import stage_01 as s1
        import stage_02 as s2
        import stage_03 as s3
        import stage_04 as s4

        problems = []
        facts = 0

        def fact(label, ok):
            nonlocal facts
            facts += 1
            if not ok:
                problems.append(label)
                print("  !! %s" % (label,))

        def must(label, ok):
            if not ok:
                raise AssertionError(label)

        tiny = configs.CONFIGS["TINY_MHA"]
        gqa = configs.CONFIGS["SEVEN_GQA"]
        D = devices.DEVICES["D_CLASS"]
        H = devices.DEVICES["H_CLASS"]
        A = devices.DEVICES["A_CLASS"]
        stub = 0
        try:
            s4.op_time(10, 10, D, "fp16")
        except NotImplementedError as error:
            must("stub message", STUB_MESSAGE in str(error))
            stub += 1
        if stub:
            print("check_04: stage 4: not implemented yet (%s)"
                  % (STUB_MESSAGE,))
            raise SystemExit(2)

        must("LAYER_OPS", s4.LAYER_OPS == ("qkv", "attn", "o", "mlp"))
        fact("FINAL_OP", s4.FINAL_OP == "head")
        must("PHASE_KEYS", s4.PHASE_KEYS
             == ("compute_ns", "memory_ns", "launch_ns", "total"))

        # --- matrix_bytes: int4 packs PER MATRIX (§2, the odd packs)
        must("int4 packs the odd matrix up", s4.matrix_bytes(5, "int4") == 3)
        must("int4 packs the even matrix exactly",
             s4.matrix_bytes(4, "int4") == 2)
        fact("fp16 doubles the count", s4.matrix_bytes(442368, "fp16") == 884736)
        fact("int8 is one byte a param", s4.matrix_bytes(442368, "int8") == 442368)
        fact("fp8 too", s4.matrix_bytes(442368, "fp8") == 442368)
        # TINY's per-matrix int4 sum is stage 1's int4 weight_bytes
        per_matrix = (6 * (s4.matrix_bytes(442368, "int4")
                           + s4.matrix_bytes(147456, "int4")
                           + s4.matrix_bytes(1769472, "int4"))
                      + s4.matrix_bytes(1572864, "int4"))
        fact("per-matrix packing beats the one-shot: TINY int4",
             per_matrix == s1.weight_bytes(tiny, "int4") == 7864320)
        _refuses(s1.PhysError, "matrix_bytes refuses negative params",
                 lambda: s4.matrix_bytes(-1, "fp16"), names=("-1",))
        _refuses(s1.PhysError, "matrix_bytes refuses unknown dtype",
                 lambda: s4.matrix_bytes(10, "fp32"), names=("fp32",))

        # --- op_time: the max of two budgets plus the launch
        # TINY qkv at D fp16: flops 884736 bytes 884736 —
        # t_compute = 884736*1e6 // (165000*1000*600) = 8
        # t_memory  = 884736*1000 // (1008*900)       = 975
        must("qkv op_time is the memory branch plus launch",
             s4.op_time(884736, 884736, D, "fp16") == 975 + 350)
        # at H the same op: t_compute = 884736e6 // (989000*1000*700) = 1,
        # t_memory = 884736000 // (3350*800) = 330; +250 launch = 580
        must("qkv at H is 580", s4.op_time(884736, 884736, H, "fp16") == 580)
        fact("head at D is memory-side: 31 vs 3467",
             s4.op_time(3145728, 3145728, D, "fp16") == 3467 + 350)
        _refuses(s1.PhysError, "op_time refuses negative flops",
                 lambda: s4.op_time(-1, 10, D, "fp16"), names=("-1",))
        _refuses(s1.PhysError, "op_time refuses negative bytes",
                 lambda: s4.op_time(10, -5, D, "fp16"), names=("-5",))
        _refuses(s1.PhysError, "op_time refuses an unknown dtype by name",
                 lambda: s4.op_time(10, 10, D, "fp32"), names=("fp32",))

        # --- classify: the tie law
        # (495000, 4536) at D fp16: t_compute = 495000e6 // 9.9e10 = 5,
        # t_memory = 4536000 // 907200 = 5 — a tie answers memory
        must("a tie is memory-bound",
             s4.classify(495000, 4536, D, "fp16") == "memory")
        must("one more flop flips it",
             s4.classify(594000, 4536, D, "fp16") == "compute")
        fact("TINY's decode qkv is memory-bound at H",
             s4.classify(884736, 884736, H, "fp16") == "memory")

        # --- ridge: flops per kilobyte, same unit as arithmetic_intensity
        must("ridge H fp16", s4.ridge(H, "fp16") == 258320)
        must("ridge H int8 doubles the peak", s4.ridge(H, "int8") == 516641)
        fact("ridge D fp16", s4.ridge(D, "fp16") == 109126)
        fact("ridge D int4 shares int8's peak",
             s4.ridge(D, "int4") == s4.ridge(D, "int8") == 218253)
        fact("ridge A fp16", s4.ridge(A, "fp16") == 132614)
        fact("ridge A int8", s4.ridge(A, "int8") == 265228)
        # the unit law: an op above the ridge classifies compute
        # FAKE's head at batch 512: flops 2*8192*256*512, bytes 2*8192*256
        # -> intensity = flops*1000//bytes = 512000 > ridge(H,fp16)=258320
        hi_flops = 2 * 8192 * 256 * 512
        hi_bytes = 2 * 8192 * 256
        fact("above the ridge is compute",
             s3.arithmetic_intensity(hi_flops, hi_bytes) > s4.ridge(H, "fp16")
             and s4.classify(hi_flops, hi_bytes, H, "fp16") == "compute")

        # --- ops_decode (§2): FAKE_MHA at batch 2, ctx 3, fp16
        fake = configs.Config("FAKE_MHA", 3, 256, 4, 2, 64, 1024, 8192)
        ops = s4.ops_decode(fake, 2, 3, "fp16")
        must("op list length is 4L+1", len(ops) == 13)
        must("qkv op", ops[0] == ("qkv", 524288, 262144))
        must("attn op — flops over H, bytes over hk, read AND store",
             ops[1] == ("attn", 6144, 4096))
        fact("o op", ops[2] == ("o", 262144, 131072))
        fact("mlp op", ops[3] == ("mlp", 3145728, 1572864))
        fact("head op once at the end", ops[-1] == ("head", 8388608, 4194304))
        fact("names repeat per layer",
             tuple(name for name, _, _ in ops)
             == (("qkv", "attn", "o", "mlp") * 3 + ("head",)))
        # GQA: the attn op keeps H's flops while its bytes ride hk
        gops = s4.ops_decode(gqa, 1, 4096, "fp16")
        must("GQA attn op", gops[1] == ("attn", 67108864, 16781312))
        # the tables sum to the earlier stages (§2 cross-law)
        t = s4.ops_decode(tiny, 1, 1024, "fp16")
        flops_sum = sum(f for _, f, _ in t)
        kv_sum = sum(b for name, _, b in t if name == "attn")
        f2 = s2.flops_token(tiny, 1024)
        b3 = s3.bytes_decode(tiny, 1024, 1, "fp16")
        must("weights-line flops sum to stage 2's total",
             flops_sum == f2["total"])
        must("attn bytes sum to stage 3's kv line",
             kv_sum == b3["kv"])
        _refuses(s1.PhysError, "ops_decode refuses batch=0",
                 lambda: s4.ops_decode(tiny, 0, 5, "fp16"), names=("batch=0",))
        _refuses(s1.PhysError, "ops_decode refuses ctx=0",
                 lambda: s4.ops_decode(tiny, 1, 0, "fp16"), names=("ctx=0",))
        _refuses(s1.PhysError, "ops_decode refuses an fp32 dtype",
                 lambda: s4.ops_decode(tiny, 1, 5, "fp32"), names=("fp32",))
        untiled = configs.Config("BADTILE", 2, 256, 5, 1, 64, 128, 128)
        _refuses(s1.PhysError, "ops_decode refuses the invalid config",
                 lambda: s4.ops_decode(untiled, 1, 5, "fp16"),
                 names=("BADTILE",))

        # --- ops_prefill (§2): fuel = prompt*batch on matmuls, quadratic
        # attention, stores-only bytes, head once per sequence
        pops = s4.ops_prefill(fake, 10, 2, "fp16")
        must("prefill qkv scales by prompt*batch",
             pops[0] == ("qkv", 2 * 131072 * 20, 262144))
        must("prefill attn is quadratic, bytes are stores only",
             pops[1] == ("attn", 204800, 10240))
        fact("prefill head is per sequence",
             pops[-1] == ("head", 2 * 8192 * 256 * 2, 4194304))
        pre = s4.ops_prefill(tiny, 1024, 1, "fp16")
        must("prefill attn bytes sum to the stored cache",
             sum(b for name, _, b in pre if name == "attn")
             == s3.bytes_prefill(tiny, 1024, 1, "fp16")["kv"])
        _refuses(s1.PhysError, "ops_prefill refuses prompt_len=0",
                 lambda: s4.ops_prefill(tiny, 0, 1, "fp16"),
                 names=("prompt_len=0",))
        _refuses(s1.PhysError, "ops_prefill refuses batch=0",
                 lambda: s4.ops_prefill(tiny, 8, 0, "fp16"),
                 names=("batch=0",))

        # --- phase_time: three sums and the max-each total
        # TINY decode batch 1 ctx 1 at D fp16 (all hand-derived):
        # compute 301, memory 34685, launch 350*25=8750, total 43435
        must("phase_time TINY D fp16 decode(1,1)",
             s4.phase_time(s4.ops_decode(tiny, 1, 1, "fp16"), D, "fp16")
             == {"compute_ns": 301, "memory_ns": 34685,
                 "launch_ns": 8750, "total": 43435})
        pt8 = s4.phase_time(s4.ops_decode(tiny, 1, 1, "int8"), D, "int8")
        must("phase_time TINY D int8 decode(1,1)",
             pt8 == {"compute_ns": 147, "memory_ns": 17345,
                     "launch_ns": 8750, "total": 26095})
        must("keys are exactly PHASE_KEYS",
             tuple(s4.phase_time(ops, D, "fp16")) == s4.PHASE_KEYS)

        # --- phase_bound: the tie law again at the phase sum
        must("phase tie is memory", s4.phase_bound(5, 5) == "memory")
        must("phase over is compute", s4.phase_bound(6, 5) == "compute")
        must("the TINY D decode phase is memory",
             s4.phase_bound(301, 34685) == "memory")

        if problems:
            raise AssertionError("%d facts failed" % (len(problems),))
        print("check_04: PASS (%d facts)" % (facts,))
        return 0
    finally:
        if root:
            sys.path[:] = [p for p in sys.path if p != course]
            shutil.rmtree(root, ignore_errors=True)

# --- stage 5 -----------------------------------------------------------------------
def check_5():
    import os
    import shutil
    import subprocess
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "transformer-inference-physics"

    STAGE = 5

    STUB_MESSAGE = "stage 5: implement prefill()"

    def _repo(start=None):
        for candidate_start in (os.environ.get("I2_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "configs.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set I2_REPO=/path/to/forja")

    def _harness_env(root):
        """Copy the repo's course into `root` with solutions/ overlaid."""
        repo = _repo(HERE)
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__"))
        overlay = os.path.join(course, "solutions")
        if os.path.isdir(overlay):
            for name in os.listdir(overlay):
                if name.startswith("stage_") and name.endswith(".py"):
                    shutil.copy2(os.path.join(overlay, name),
                                 os.path.join(course, name))

    def _refuses(exc, what, call, names=()):
        """`call()` must raise `exc` naming every string in `names`."""
        try:
            call()
        except exc as problem:
            text = str(problem)
            missing = [w for w in tuple(names) if w not in text]
            if missing:
                raise AssertionError(
                    "%s: refusal %r does not name %s"
                    % (what, text, missing))
        else:
            raise AssertionError("%s: no refusal" % (what,))

    def _template_verdict():
        """The template must be the exit-2 refusal, with its own message."""
        repo = _repo(HERE)
        root = tempfile.mkdtemp(prefix="i2_check05_tpl_")
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__",
                                                      "solutions"))
        try:
            code = ("import sys; sys.path.insert(0, %r)\n"
                    "import configs, devices, stage_05 as s5\n"
                    "try:\n"
                    "    s5.prefill(configs.CONFIGS['TINY_MHA'],\n"
                    "               devices.DEVICES['D_CLASS'], 'fp16', 1, 1)\n"
                    "except NotImplementedError as e:\n"
                    "    assert 'implement' in str(e), e\n"
                    "    print('not implemented yet')\n"
                    "    raise SystemExit(42)\n"
                    "raise SystemExit(7)\n" % (course,))
            proc = subprocess.run([sys.executable, "-c", code],
                                  capture_output=True, text=True, timeout=120)
            if proc.returncode == 42 and "not implemented yet" in proc.stdout:
                return 2, proc.stdout.strip()
            return 1, "template did not raise the stub: %s" % (proc.stderr,)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    ambient = next((p for p in sys.path
                    if os.path.isfile(os.path.join(p, "configs.py"))
                    and os.path.isfile(os.path.join(p, "stage_05.py"))),
                    None)
    if ambient is not None:
        root = None
        course = ambient
    else:
        root = tempfile.mkdtemp(prefix="i2_check05_env_")
        course = os.path.join(root, COURSE)
        _harness_env(root)
        sys.path.insert(0, course)
    try:
        import configs
        import devices
        import trace
        import stage_01 as s1
        import stage_04 as s4
        import stage_05 as s5

        problems = []
        facts = 0

        def fact(label, ok):
            nonlocal facts
            facts += 1
            if not ok:
                problems.append(label)
                print("  !! %s" % (label,))

        def must(label, ok):
            if not ok:
                raise AssertionError(label)

        tiny = configs.CONFIGS["TINY_MHA"]
        gqa = configs.CONFIGS["SEVEN_GQA"]
        D = devices.DEVICES["D_CLASS"]
        H = devices.DEVICES["H_CLASS"]
        stub = 0
        try:
            s5.prefill(tiny, D, "fp16", 1, 1)
        except NotImplementedError as error:
            must("stub message", STUB_MESSAGE in str(error))
            stub += 1
        if stub:
            print("check_05: stage 5: not implemented yet (%s)"
                  % (STUB_MESSAGE,))
            raise SystemExit(2)

        must("PREFILL_KEYS", s5.PREFILL_KEYS
             == ("compute_ns", "memory_ns", "launch_ns", "total", "bound"))

        fake = configs.Config("FAKE_MHA", 3, 256, 4, 2, 64, 1024, 8192)
        # FAKE prefill D fp16 p=5 b=2, hand-summed per op (§2):
        # compute 675, memory 11133, launch 350*13 = 4550, total 15683
        must("FAKE prefill D fp16 p5 b2",
             s5.prefill(fake, D, "fp16", 5, 2)
             == {"compute_ns": 675, "memory_ns": 11133,
                 "launch_ns": 4550, "total": 15683, "bound": "memory"})
        must("keys are exactly PREFILL_KEYS",
             tuple(s5.prefill(tiny, D, "fp16", 1, 1)) == s5.PREFILL_KEYS)

        # TINY at H, one token: compute 40, memory 11733, launch
        # 250*25 = 6250, total 17983 — the tiny prompt is memory-bound,
        # the honest exception to the stage's verdict
        must("TINY prefill H fp16 p1 b1",
             s5.prefill(tiny, H, "fp16", 1, 1)
             == {"compute_ns": 40, "memory_ns": 11733,
                 "launch_ns": 6250, "total": 17983, "bound": "memory"})
        # TINY at D, 1024 tokens: compute 390469 beats memory 45065 —
        # the slow device's ridge is low enough for the quadratic
        # attention to clear it: total 402655, bound compute
        must("TINY prefill D fp16 p1024 b1",
             s5.prefill(tiny, D, "fp16", 1024, 1)
             == {"compute_ns": 390469, "memory_ns": 45065,
                 "launch_ns": 8750, "total": 402655,
                 "bound": "compute"})
        # SEVEN_GQA at H, 4096 tokens: 79937104 ns, compute-bound
        fact("GQA prefill H fp16 p4096 b1",
             s5.prefill(gqa, H, "fp16", 4096, 1)
             == {"compute_ns": 79807418, "memory_ns": 4529974,
                 "launch_ns": 32250, "total": 79937104,
                 "bound": "compute"})
        # the long prompt: TINY 131072 at H — the quadratic dominates
        fact("TINY prefill H fp16 p131072 is compute-bound",
             s5.prefill(tiny, H, "fp16", 131072, 1)
             == {"compute_ns": 234061132, "memory_ns": 462459,
                 "launch_ns": 6250, "total": 234068551,
                 "bound": "compute"})

        # --- the table is exactly stage 4's ops_prefill through phase_time
        for cfg, dev, dt, p, b in ((fake, D, "fp16", 5, 2),
                                   (tiny, H, "fp16", 1024, 1),
                                   (gqa, H, "int8", 4096, 1)):
            ph = s4.phase_time(s4.ops_prefill(cfg, p, b, dt), dev, dt)
            pf = s5.prefill(cfg, dev, dt, p, b)
            fact("prefill = phase_time(ops_prefill) at %s/%s/%s p%d b%d"
                 % (cfg.name, dev.name, dt, p, b),
                 (pf["compute_ns"], pf["memory_ns"], pf["launch_ns"],
                  pf["total"])
                 == (ph["compute_ns"], ph["memory_ns"], ph["launch_ns"],
                     ph["total"])
                 and pf["bound"] == s4.phase_bound(ph["compute_ns"],
                                                   ph["memory_ns"]))

        # --- no probe tax: the model's number is the profiler's minus
        # exactly one PROBE_NS (§3.5/§3.10)
        must("PROBE_NS is the world's 1500", trace.PROBE_NS == 1500)
        for name, dn, wl, dt in (("TINY_MHA", "D_CLASS", "W_A", "fp16"),
                                 ("TINY_MHA", "H_CLASS", "W_A", "fp16"),
                                 ("TINY_MHA", "H_CLASS", "W_F", "fp16"),
                                 ("SEVEN_GQA", "H_CLASS", "W_B", "int8")):
            cfg = configs.CONFIGS[name]
            wlrow = trace.WORKLOADS[wl]
            model = s5.prefill(cfg, devices.DEVICES[dn], dt,
                               wlrow.prompt, wlrow.batch)
            measured = trace.measure("ttft", name, dn, wl, dt)
            fact("model + one tax = profiler at %s %s %s" % (name, dn, wl),
                 model["total"] + trace.PROBE_NS == measured)
            fact("bound agrees with the world at %s %s %s" % (name, dn, wl),
                 model["bound"] == trace.bound("ttft", name, dn, wl, dt))
        fact("compute never exceeds total",
             all(s5.prefill(c, D, "fp16", 64, 1)[k]
                 <= s5.prefill(c, D, "fp16", 64, 1)["total"]
                 for c in configs.CONFIGS.values()
                 for k in ("compute_ns", "memory_ns", "launch_ns")))

        # --- refusals
        _refuses(s1.PhysError, "prompt_len=0 refused",
                 lambda: s5.prefill(tiny, D, "fp16", 0, 1),
                 names=("prompt_len", "0"))
        _refuses(s1.PhysError, "batch=0 refused",
                 lambda: s5.prefill(tiny, D, "fp16", 8, 0),
                 names=("batch", "0"))
        _refuses(s1.PhysError, "unknown dtype refused",
                 lambda: s5.prefill(tiny, D, "fp32", 8, 1),
                 names=("fp32",))
        _refuses(s1.PhysError, "unknown device refused by name",
                 lambda: s5.prefill(
                     tiny, devices.Device("TINY_ACCEL", 1, 1, 1, 1, 1, 1),
                     "fp16", 8, 1),
                 names=("TINY_ACCEL", "D_CLASS"))
        untiled = configs.Config("BADTILE", 2, 256, 5, 1, 64, 128, 128)
        _refuses(s1.PhysError, "invalid config refused",
                 lambda: s5.prefill(untiled, D, "fp16", 8, 1),
                 names=("BADTILE",))

        if problems:
            raise AssertionError("%d facts failed" % (len(problems),))
        print("check_05: PASS (%d facts)" % (facts,))
        return 0
    finally:
        if root:
            sys.path[:] = [p for p in sys.path if p != course]
            shutil.rmtree(root, ignore_errors=True)

# --- stage 6 -----------------------------------------------------------------------
def check_6():
    import os
    import shutil
    import subprocess
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "transformer-inference-physics"

    STAGE = 6

    STUB_MESSAGE = "stage 6: implement decode()"

    def _repo(start=None):
        for candidate_start in (os.environ.get("I2_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "configs.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set I2_REPO=/path/to/forja")

    def _harness_env(root):
        """Copy the repo's course into `root` with solutions/ overlaid."""
        repo = _repo(HERE)
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__"))
        overlay = os.path.join(course, "solutions")
        if os.path.isdir(overlay):
            for name in os.listdir(overlay):
                if name.startswith("stage_") and name.endswith(".py"):
                    shutil.copy2(os.path.join(overlay, name),
                                 os.path.join(course, name))

    def _refuses(exc, what, call, names=()):
        """`call()` must raise `exc` naming every string in `names`."""
        try:
            call()
        except exc as problem:
            text = str(problem)
            missing = [w for w in tuple(names) if w not in text]
            if missing:
                raise AssertionError(
                    "%s: refusal %r does not name %s"
                    % (what, text, missing))
        else:
            raise AssertionError("%s: no refusal" % (what,))

    def _template_verdict():
        """The template must be the exit-2 refusal, with its own message."""
        repo = _repo(HERE)
        root = tempfile.mkdtemp(prefix="i2_check06_tpl_")
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__",
                                                      "solutions"))
        try:
            code = ("import sys; sys.path.insert(0, %r)\n"
                    "import configs, devices, stage_06 as s6\n"
                    "try:\n"
                    "    s6.decode(configs.CONFIGS['TINY_MHA'],\n"
                    "              devices.DEVICES['D_CLASS'], 'fp16', 1, 1)\n"
                    "except NotImplementedError as e:\n"
                    "    assert 'implement' in str(e), e\n"
                    "    print('not implemented yet')\n"
                    "    raise SystemExit(42)\n"
                    "raise SystemExit(7)\n" % (course,))
            proc = subprocess.run([sys.executable, "-c", code],
                                  capture_output=True, text=True, timeout=120)
            if proc.returncode == 42 and "not implemented yet" in proc.stdout:
                return 2, proc.stdout.strip()
            return 1, "template did not raise the stub: %s" % (proc.stderr,)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    ambient = next((p for p in sys.path
                    if os.path.isfile(os.path.join(p, "configs.py"))
                    and os.path.isfile(os.path.join(p, "stage_06.py"))),
                    None)
    if ambient is not None:
        root = None
        course = ambient
    else:
        root = tempfile.mkdtemp(prefix="i2_check06_env_")
        course = os.path.join(root, COURSE)
        _harness_env(root)
        sys.path.insert(0, course)
    try:
        import configs
        import devices
        import trace
        import stage_01 as s1
        import stage_03 as s3
        import stage_04 as s4
        import stage_06 as s6

        problems = []
        facts = 0

        def fact(label, ok):
            nonlocal facts
            facts += 1
            if not ok:
                problems.append(label)
                print("  !! %s" % (label,))

        def must(label, ok):
            if not ok:
                raise AssertionError(label)

        tiny = configs.CONFIGS["TINY_MHA"]
        gqa = configs.CONFIGS["SEVEN_GQA"]
        D = devices.DEVICES["D_CLASS"]
        H = devices.DEVICES["H_CLASS"]
        stub = 0
        try:
            s6.decode(tiny, D, "fp16", 1, 1)
        except NotImplementedError as error:
            must("stub message", STUB_MESSAGE in str(error))
            stub += 1
        if stub:
            print("check_06: stage 6: not implemented yet (%s)"
                  % (STUB_MESSAGE,))
            raise SystemExit(2)

        must("DECODE_KEYS", s6.DECODE_KEYS
             == ("compute_ns", "memory_ns", "launch_ns", "total", "bound"))

        fake = configs.Config("FAKE_MHA", 3, 256, 4, 2, 64, 1024, 8192)
        # FAKE decode D fp16 ctx=3 batch=2, hand-summed per op (§2):
        # compute 198, memory 11130, launch 350*13 = 4550, total 15680
        must("FAKE decode D fp16 ctx3 b2",
             s6.decode(fake, D, "fp16", 3, 2)
             == {"compute_ns": 198, "memory_ns": 11130,
                 "launch_ns": 4550, "total": 15680, "bound": "memory"})
        must("keys are exactly DECODE_KEYS",
             tuple(s6.decode(tiny, D, "fp16", 1, 1)) == s6.DECODE_KEYS)

        # TINY at D, one token of context: compute 301 vs memory 34685 —
        # a hundred-fold idle silicon, launch 8750, total 43435
        must("TINY decode D fp16 ctx1 b1",
             s6.decode(tiny, D, "fp16", 1, 1)
             == {"compute_ns": 301, "memory_ns": 34685,
                 "launch_ns": 8750, "total": 43435, "bound": "memory"})
        # the amortization lesson (§3.6): batch 8 over the same one-token
        # cache barely moves the step: weights read once, memory 34829
        fact("TINY decode D fp16 ctx1 b8",
             s6.decode(tiny, D, "fp16", 1, 8)
             == {"compute_ns": 2528, "memory_ns": 34829,
                 "launch_ns": 8750, "total": 43579, "bound": "memory"})
        fact("eight sequences cost 3% more than one",
             43579 * 100 // 43435 == 100)
        # the same step on the fast device: memory 15255, total 21505
        fact("TINY decode H fp16 ctx1024 b1",
             s6.decode(tiny, H, "fp16", 1024, 1)
             == {"compute_ns": 52, "memory_ns": 15255,
                 "launch_ns": 6250, "total": 21505, "bound": "memory"})
        # SEVEN_GQA at H: the cache narrows with hk, the step follows
        fact("GQA decode H fp16 ctx1 b1",
             s6.decode(gqa, H, "fp16", 1, 1)
             == {"compute_ns": 16698, "memory_ns": 4329750,
                 "launch_ns": 32250, "total": 4362000, "bound": "memory"})
        fact("GQA decode H int8 ctx1024 b1",
             s6.decode(gqa, H, "int8", 1024, 1)
             == {"compute_ns": 8733, "memory_ns": 2214923,
                 "launch_ns": 32250, "total": 2247173, "bound": "memory"})
        # monotone in the cache: the rent grows every step
        t1 = s6.decode(tiny, D, "fp16", 1279, 1)["total"]
        must("the last W_A step costs 56419 ns of model",
             t1 == 56419)
        fact("the step grows with the context",
             s6.decode(tiny, D, "fp16", 1024, 1)["total"] < t1
             and s6.decode(tiny, D, "fp16", 2048, 1)["total"] > t1)

        # --- the table is exactly stage 4's ops_decode through phase_time
        for cfg, dev, dt, ctx, b in ((fake, D, "fp16", 3, 2),
                                     (tiny, H, "fp16", 1024, 1),
                                     (gqa, H, "int8", 1024, 1)):
            ph = s4.phase_time(s4.ops_decode(cfg, b, ctx, dt), dev, dt)
            dc = s6.decode(cfg, dev, dt, ctx, b)
            fact("decode = phase_time(ops_decode) at %s/%s/%s ctx%d b%d"
                 % (cfg.name, dev.name, dt, ctx, b),
                 (dc["compute_ns"], dc["memory_ns"], dc["launch_ns"],
                  dc["total"])
                 == (ph["compute_ns"], ph["memory_ns"], ph["launch_ns"],
                     ph["total"])
                 and dc["bound"] == s4.phase_bound(ph["compute_ns"],
                                                   ph["memory_ns"]))

        # --- the ITL law (§3.6/§3.10): the mean over the schedule, one
        # probe tax on the mean, and the batch-1 step IS its own mean
        must("PROBE_NS is the world's 1500", trace.PROBE_NS == 1500)
        # W_A at D: ctx runs 1024..1279; the hand-summed schedule is
        # 14111224 ns, //256 + 1500 = 56621, exactly trace.measure
        total = 0
        for i in range(trace.WORKLOADS["W_A"].gen):
            total += s6.decode(tiny, D, "fp16",
                               1024 + i, 1)["total"]
        fact("the W_A schedule sums to 14111224 ns of model",
             total == 14111224)
        fact("the mean plus one tax is the profiler's ITL",
             total // 256 + trace.PROBE_NS
             == trace.measure("itl", "TINY_MHA", "D_CLASS", "W_A", "fp16"))
        # the last step's bound is the world's itl bound
        fact("the last step's bound is the world's verdict",
             s6.decode(tiny, D, "fp16", 1279, 1)["bound"]
             == trace.bound("itl", "TINY_MHA", "D_CLASS", "W_A", "fp16"))
        # the mirror lesson: push the batch past stage 8's crossover and
        # the SAME device and context flip to compute — a hardcoded
        # "memory" verdict dies here
        must("TINY decode D fp16 ctx1 b128 is compute-bound",
             s6.decode(tiny, D, "fp16", 1, 128)
             == {"compute_ns": 40667, "memory_ns": 37265,
                 "launch_ns": 8750, "total": 52009, "bound": "compute"})

        # --- refusals
        _refuses(s1.PhysError, "ctx=0 refused",
                 lambda: s6.decode(tiny, D, "fp16", 0, 1), names=("ctx", "0"))
        _refuses(s1.PhysError, "batch=0 refused",
                 lambda: s6.decode(tiny, D, "fp16", 5, 0), names=("batch", "0"))
        _refuses(s1.PhysError, "unknown dtype refused",
                 lambda: s6.decode(tiny, D, "fp32", 5, 1), names=("fp32",))
        _refuses(s1.PhysError, "unknown device refused by name",
                 lambda: s6.decode(
                     tiny, devices.Device("TINY_ACCEL", 1, 1, 1, 1, 1, 1),
                     "fp16", 5, 1),
                 names=("TINY_ACCEL", "D_CLASS"))
        untiled = configs.Config("BADTILE", 2, 256, 5, 1, 64, 128, 128)
        _refuses(s1.PhysError, "invalid config refused",
                 lambda: s6.decode(untiled, D, "fp16", 5, 1),
                 names=("BADTILE",))

        if problems:
            raise AssertionError("%d facts failed" % (len(problems),))
        print("check_06: PASS (%d facts)" % (facts,))
        return 0
    finally:
        if root:
            sys.path[:] = [p for p in sys.path if p != course]
            shutil.rmtree(root, ignore_errors=True)

# --- stage 7 -----------------------------------------------------------------------
def check_7():
    import os
    import shutil
    import subprocess
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "transformer-inference-physics"

    STAGE = 7

    STUB_MESSAGE = "stage 7: implement cache_table()"

    def _repo(start=None):
        for candidate_start in (os.environ.get("I2_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "configs.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set I2_REPO=/path/to/forja")

    def _harness_env(root):
        """Copy the repo's course into `root` with solutions/ overlaid."""
        repo = _repo(HERE)
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__"))
        overlay = os.path.join(course, "solutions")
        if os.path.isdir(overlay):
            for name in os.listdir(overlay):
                if name.startswith("stage_") and name.endswith(".py"):
                    shutil.copy2(os.path.join(overlay, name),
                                 os.path.join(course, name))

    def _refuses(exc, what, call, names=()):
        """`call()` must raise `exc` naming every string in `names`."""
        try:
            call()
        except exc as problem:
            text = str(problem)
            missing = [w for w in tuple(names) if w not in text]
            if missing:
                raise AssertionError(
                    "%s: refusal %r does not name %s"
                    % (what, text, missing))
        else:
            raise AssertionError("%s: no refusal" % (what,))

    def _template_verdict():
        """The template must be the exit-2 refusal, with its own message."""
        repo = _repo(HERE)
        root = tempfile.mkdtemp(prefix="i2_check07_tpl_")
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__",
                                                      "solutions"))
        try:
            code = ("import sys; sys.path.insert(0, %r)\n"
                    "import stage_07 as s7\n"
                    "try:\n"
                    "    s7.cache_table()\n"
                    "except NotImplementedError as e:\n"
                    "    assert 'implement' in str(e), e\n"
                    "    print('not implemented yet')\n"
                    "    raise SystemExit(42)\n"
                    "raise SystemExit(7)\n" % (course,))
            proc = subprocess.run([sys.executable, "-c", code],
                                  capture_output=True, text=True, timeout=120)
            if proc.returncode == 42 and "not implemented yet" in proc.stdout:
                return 2, proc.stdout.strip()
            return 1, "template did not raise the stub: %s" % (proc.stderr,)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    ambient = next((p for p in sys.path
                    if os.path.isfile(os.path.join(p, "configs.py"))
                    and os.path.isfile(os.path.join(p, "stage_07.py"))),
                    None)
    if ambient is not None:
        root = None
        course = ambient
    else:
        root = tempfile.mkdtemp(prefix="i2_check07_env_")
        course = os.path.join(root, COURSE)
        _harness_env(root)
        sys.path.insert(0, course)
    try:
        import configs
        import devices
        import stage_01 as s1
        import stage_03 as s3
        import stage_07 as s7

        problems = []
        facts = 0

        def fact(label, ok):
            nonlocal facts
            facts += 1
            if not ok:
                problems.append(label)
                print("  !! %s" % (label,))

        def must(label, ok):
            if not ok:
                raise AssertionError(label)

        tiny = configs.CONFIGS["TINY_MHA"]
        mha = configs.CONFIGS["SEVEN_MHA"]
        gqa = configs.CONFIGS["SEVEN_GQA"]
        mqa = configs.CONFIGS["SEVEN_MQA"]
        big = configs.CONFIGS["BIG_GQA"]
        D = devices.DEVICES["D_CLASS"]
        H = devices.DEVICES["H_CLASS"]
        stub = 0
        try:
            s7.cache_table()
        except NotImplementedError as error:
            must("stub message", STUB_MESSAGE in str(error))
            stub += 1
        if stub:
            print("check_07: stage 7: not implemented yet (%s)"
                  % (STUB_MESSAGE,))
            raise SystemExit(2)

        must("CACHE_KEYS", s7.CACHE_KEYS
             == ("config", "kv_bytes_per_token", "kv_bytes_at_4096",
                 "kv_bytes_at_131072"))

        # --- cache_table: the whole world's rent, five hand-written rows
        # (§2: rent = 4*hk*h_d*L; 4096 and 131072 are the course's two
        # contexts — everything fits at one, MHA dies at the other)
        must("cache_table is the five world rows in order",
             s7.cache_table() == (
                 ("TINY_MHA", 9216, 37748736, 1207959552),
                 ("SEVEN_MHA", 524288, 2147483648, 68719476736),
                 ("SEVEN_GQA", 131072, 536870912, 17179869184),
                 ("SEVEN_MQA", 16384, 67108864, 2147483648),
                 ("BIG_GQA", 327680, 1342177280, 42949672960)))
        fact("every row's contexts are the rent times the context",
             all(row[2] == row[1] * 4096 and row[3] == row[1] * 131072
                 for row in s7.cache_table()))

        # --- cache_life: the context where the rent catches the weights
        # TINY fp16: 31457280 // 9216 = 3413 — the weights' own length
        must("TINY fp16 life", s7.cache_life(tiny, "fp16") == 3413)
        # int8 halves the weights, so the catch-up halves too: 1706
        must("TINY int8 life is half", s7.cache_life(tiny, "int8") == 1706)
        # int4 packs PER MATRIX (§1's law rides the weights side):
        # weight_bytes int4 // rent — computed in the same floor
        must("TINY int4 life", s7.cache_life(tiny, "int4") == 853)
        fact("the world's lives",
             [s7.cache_life(c, "fp16") for c in (gqa, mha, mqa, big)]
             == [88528, 25204, 679552, 424192])
        # the GQA lesson in one integer: the rent is a quarter of MHA's
        # while the weights barely move, so the life multiplies
        fact("GQA lives 3.5 times MHA's context",
             s7.cache_life(gqa, "fp16") > 3 * s7.cache_life(mha, "fp16"))
        fact("MQA lives eight times GQA's",
             s7.cache_life(mqa, "fp16") > 7 * s7.cache_life(gqa, "fp16"))
        _refuses(s1.PhysError, "cache_life refuses a bad dtype",
                 lambda: s7.cache_life(tiny, "fp32"), names=("fp32",))
        untiled = configs.Config("BADTILE", 2, 256, 5, 1, 64, 128, 128)
        _refuses(s1.PhysError, "cache_life refuses the invalid config",
                 lambda: s7.cache_life(untiled, "fp16"), names=("BADTILE",))

        # --- vram_batch_edge (§2): free // whole-stack cache, 0 walls
        # TINY at D fp16, ctx 1024: free = 25769803776 - 31457280
        # = 25738346496; cache at 1024 = 9216*1024 = 9437184; // = 2727
        must("TINY D fp16 edge at 1024",
             s7.vram_batch_edge(tiny, D, "fp16", 1024) == 2727)
        # the rent is linear: a 4x context quarters the edge — 681
        must("TINY D fp16 edge at 4096",
             s7.vram_batch_edge(tiny, D, "fp16", 4096) == 681)
        # quantizing the weights GROWS the edge: int4 frees 23592960
        # more bytes: (25769803776 - 7864320) // 9437184 = 2729
        fact("TINY D int4 edge is two batches larger",
             s7.vram_batch_edge(tiny, D, "int4", 1024) == 2729)
        # BIG_GQA int8 at H: free = 85899345920 - 69499617280
        # = 16399728640; cache at 1280 = 327680*1280 = 419430400; //= 39
        fact("BIG H int8 edge at 1280",
             s7.vram_batch_edge(big, H, "int8", 1280) == 39)
        # the 0 law: BIG's fp16 weights (138999234560) exceed even H's
        # 80 GiB — the wall IS the answer, not a refusal
        fact("BIG on H fp16 at any context is 0",
             s7.vram_batch_edge(big, H, "fp16", 1024) == 0
             and s7.vram_batch_edge(big, H, "fp16", 1) == 0)
        # and the same config on int8 fits: 39 at 1280
        fact("quantization is what moved the wall",
             s7.vram_batch_edge(big, H, "int8", 1280) > 0)
        _refuses(s1.PhysError, "edge refuses ctx=0",
                 lambda: s7.vram_batch_edge(tiny, D, "fp16", 0),
                 names=("ctx=0", "edge"))
        _refuses(s1.PhysError, "edge refuses a bad dtype",
                 lambda: s7.vram_batch_edge(tiny, D, "fp32", 1),
                 names=("fp32",))
        _refuses(s1.PhysError, "edge refuses an unknown device by name",
                 lambda: s7.vram_batch_edge(
                     tiny, devices.Device("TINY_ACCEL", 1, 1, 1, 1, 1, 1),
                     "fp16", 1), names=("TINY_ACCEL",))

        if problems:
            raise AssertionError("%d facts failed" % (len(problems),))
        print("check_07: PASS (%d facts)" % (facts,))
        return 0
    finally:
        if root:
            sys.path[:] = [p for p in sys.path if p != course]
            shutil.rmtree(root, ignore_errors=True)

# --- stage 8 -----------------------------------------------------------------------
def check_8():
    import os
    import shutil
    import subprocess
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "transformer-inference-physics"

    STAGE = 8

    STUB_MESSAGE = "stage 8: implement crossover_batch()"

    def _repo(start=None):
        for candidate_start in (os.environ.get("I2_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "configs.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set I2_REPO=/path/to/forja")

    def _harness_env(root):
        """Copy the repo's course into `root` with solutions/ overlaid."""
        repo = _repo(HERE)
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__"))
        overlay = os.path.join(course, "solutions")
        if os.path.isdir(overlay):
            for name in os.listdir(overlay):
                if name.startswith("stage_") and name.endswith(".py"):
                    shutil.copy2(os.path.join(overlay, name),
                                 os.path.join(course, name))

    def _refuses(exc, what, call, names=()):
        """`call()` must raise `exc` naming every string in `names`."""
        try:
            call()
        except exc as problem:
            text = str(problem)
            missing = [w for w in tuple(names) if w not in text]
            if missing:
                raise AssertionError(
                    "%s: refusal %r does not name %s"
                    % (what, text, missing))
        else:
            raise AssertionError("%s: no refusal" % (what,))

    def _template_verdict():
        """The template must be the exit-2 refusal, with its own message."""
        repo = _repo(HERE)
        root = tempfile.mkdtemp(prefix="i2_check08_tpl_")
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__",
                                                      "solutions"))
        try:
            code = ("import sys; sys.path.insert(0, %r)\n"
                    "import configs, devices, stage_08 as s8\n"
                    "try:\n"
                    "    s8.crossover_batch(configs.CONFIGS['TINY_MHA'],\n"
                    "                         devices.DEVICES['D_CLASS'], 'fp16')\n"
                    "except NotImplementedError as e:\n"
                    "    assert 'implement' in str(e), e\n"
                    "    print('not implemented yet')\n"
                    "    raise SystemExit(42)\n"
                    "raise SystemExit(7)\n" % (course,))
            proc = subprocess.run([sys.executable, "-c", code],
                                  capture_output=True, text=True, timeout=120)
            if proc.returncode == 42 and "not implemented yet" in proc.stdout:
                return 2, proc.stdout.strip()
            return 1, "template did not raise the stub: %s" % (proc.stderr,)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    ambient = next((p for p in sys.path
                    if os.path.isfile(os.path.join(p, "configs.py"))
                    and os.path.isfile(os.path.join(p, "stage_08.py"))),
                    None)
    if ambient is not None:
        root = None
        course = ambient
    else:
        root = tempfile.mkdtemp(prefix="i2_check08_env_")
        course = os.path.join(root, COURSE)
        _harness_env(root)
        sys.path.insert(0, course)
    try:
        import configs
        import devices
        import trace
        import stage_01 as s1
        import stage_04 as s4
        import stage_06 as s6
        import stage_08 as s8

        problems = []
        facts = 0

        def fact(label, ok):
            nonlocal facts
            facts += 1
            if not ok:
                problems.append(label)
                print("  !! %s" % (label,))

        def must(label, ok):
            if not ok:
                raise AssertionError(label)

        tiny = configs.CONFIGS["TINY_MHA"]
        mha = configs.CONFIGS["SEVEN_MHA"]
        gqa = configs.CONFIGS["SEVEN_GQA"]
        mqa = configs.CONFIGS["SEVEN_MQA"]
        big = configs.CONFIGS["BIG_GQA"]
        D = devices.DEVICES["D_CLASS"]
        H = devices.DEVICES["H_CLASS"]
        A = devices.DEVICES["A_CLASS"]
        stub = 0
        try:
            s8.crossover_batch(tiny, D, "fp16")
        except NotImplementedError as error:
            must("stub message", STUB_MESSAGE in str(error))
            stub += 1
        if stub:
            print("check_08: stage 8: not implemented yet (%s)"
                  % (STUB_MESSAGE,))
            raise SystemExit(2)

        fake = configs.Config("FAKE_MHA", 3, 256, 4, 2, 64, 1024, 8192)
        # FAKE at D fp16: mlp flops 6*256*1024*b, bytes 2*3*256*1024 —
        # the ratio t_memory/t_compute lands on the same first batch as
        # every other (d, dff) in this course's fp16-on-D lineup: 110
        must("FAKE crossover at D fp16", s8.crossover_batch(fake, D,
                                                            "fp16") == 110)

        # --- the crossover rows, hand-derived (§2: smallest b with
        # t_compute(6*d*dff*b) > t_memory(mlp bytes))
        # H fp16: mlp bytes 2*3*4096*11008 = 270532608, t_memory =
        # 270532608000 // 2680000 = 100945 ns; t_compute at 258 = 100819
        # (still memory), at 259 = 101210 (compute) — the boundary walk
        must("SEVEN crossover on H fp16 is 259",
             s8.crossover_batch(gqa, H, "fp16") == 259)
        must("one below is still memory-bound",
             s4.classify(6 * 4096 * 11008 * 258, 2 * 3 * 4096 * 11008,
                         H, "fp16") == "memory"
             and s4.classify(6 * 4096 * 11008 * 259, 2 * 3 * 4096 * 11008,
                             H, "fp16") == "compute")
        # the heads are invisible: MHA, GQA, MQA and BIG share d and dff
        fact("the crossover ignores n_heads and n_kv_heads",
             s8.crossover_batch(mha, H, "fp16") == 259
             and s8.crossover_batch(mqa, H, "fp16") == 259
             and s8.crossover_batch(big, H, "fp16") == 259)
        # int8: double peak, half bytes — (C*2000*ec) vs (b/2*1000): the
        # same crossover 259 (the two effects cancel)
        fact("int8 cancels: still 259",
             s8.crossover_batch(gqa, H, "int8") == 259)
        # int4: the same doubled peak, the mlp packs to (p+1)//2: the
        # crossover halves — 130
        must("int4 doubles the ridge, halves the crossover",
             s8.crossover_batch(gqa, H, "int4") == 130)
        fact("D-class fp16 crossover is 110 for every world config",
             [s8.crossover_batch(c, D, "fp16")
              for c in (tiny, mha, gqa, mqa, big)] == [110] * 5)
        fact("A-class fp16 crossover is 133",
             s8.crossover_batch(gqa, A, "fp16") == 133
             and s8.crossover_batch(tiny, A, "fp16") == 133)

        # --- batch_curve (§3.8): stage 6's total over the ladder
        # TINY D fp16 ctx=1, hand-computed step totals per batch:
        must("curve TINY D fp16 ctx1",
             s8.batch_curve(tiny, D, "fp16", 1)
             == {1: 43435, 2: 43453, 4: 43495, 8: 43579, 16: 43741,
                 32: 44065, 64: 44713, 128: 52009, 256: 95280,
                 512: 181828})
        must("curve TINY H fp16 ctx1024",
             s8.batch_curve(tiny, H, "fp16", 1024)
             == {1: 21505, 2: 25027, 4: 32077, 8: 46177, 16: 74377,
                 32: 130771, 64: 243565, 128: 469153, 256: 920323,
                 512: 1834190})
        # the ladder is the world's
        must("the curve walks trace.BATCHES",
             tuple(s8.batch_curve(fake, D, "fp16", 5)) == trace.BATCHES)
        # the curve IS stage 6
        fact("curve values are decode totals",
             all(s8.batch_curve(tiny, H, "fp16", 1024)[b]
                 == s6.decode(tiny, H, "fp16", 1024, b)["total"]
                 for b in trace.BATCHES))
        # the curve follows the weight dtype: int8 halves the memory
        # branch's bytes at ctx=1 — the first step is 26095, not 43435
        fact("curve TINY D int8 ctx1 b1 is the int8 step",
             s8.batch_curve(tiny, D, "int8", 1)[1] == 26095)
        # the kink law: below the crossover the step barely moves; at
        # and past it, doubling the batch roughly doubles the step
        c1 = s8.batch_curve(tiny, H, "fp16", 1024)
        fact("the flat part is flat", c1[8] * 100 // c1[1] < 250)
        fact("the steep part nearly doubles per batch doubling",
             c1[512] * 100 // c1[256] > 190)

        # --- refusals
        _refuses(s1.PhysError, "crossover refuses an invalid config",
                 lambda: s8.crossover_batch(
                     configs.Config("BADTILE", 2, 256, 5, 1, 64, 128, 128),
                     D, "fp16"), names=("BADTILE",))
        _refuses(s1.PhysError, "crossover refuses an unknown dtype",
                 lambda: s8.crossover_batch(tiny, D, "fp32"),
                 names=("fp32",))
        _refuses(s1.PhysError, "crossover refuses an unknown device",
                 lambda: s8.crossover_batch(
                     tiny, devices.Device("TINY_ACCEL", 1, 1, 1, 1, 1, 1),
                     "fp16"), names=("TINY_ACCEL",))
        _refuses(s1.PhysError, "curve refuses ctx=0",
                 lambda: s8.batch_curve(tiny, D, "fp16", 0),
                 names=("ctx=0", "curve"))
        _refuses(s1.PhysError, "curve refuses an unknown device",
                 lambda: s8.batch_curve(
                     tiny, devices.Device("TINY_ACCEL", 1, 1, 1, 1, 1, 1),
                     "fp16", 5), names=("TINY_ACCEL",))

        if problems:
            raise AssertionError("%d facts failed" % (len(problems),))
        print("check_08: PASS (%d facts)" % (facts,))
        return 0
    finally:
        if root:
            sys.path[:] = [p for p in sys.path if p != course]
            shutil.rmtree(root, ignore_errors=True)

# --- stage 9 -----------------------------------------------------------------------
def check_9():
    import os
    import shutil
    import subprocess
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "transformer-inference-physics"

    STAGE = 9

    STUB_MESSAGE = "stage 9: implement quant_weights()"

    def _repo(start=None):
        for candidate_start in (os.environ.get("I2_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "configs.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set I2_REPO=/path/to/forja")

    def _harness_env(root):
        """Copy the repo's course into `root` with solutions/ overlaid."""
        repo = _repo(HERE)
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__"))
        overlay = os.path.join(course, "solutions")
        if os.path.isdir(overlay):
            for name in os.listdir(overlay):
                if name.startswith("stage_") and name.endswith(".py"):
                    shutil.copy2(os.path.join(overlay, name),
                                 os.path.join(course, name))

    def _refuses(exc, what, call, names=()):
        """`call()` must raise `exc` naming every string in `names`."""
        try:
            call()
        except exc as problem:
            text = str(problem)
            missing = [w for w in tuple(names) if w not in text]
            if missing:
                raise AssertionError(
                    "%s: refusal %r does not name %s"
                    % (what, text, missing))
        else:
            raise AssertionError("%s: no refusal" % (what,))

    def _template_verdict():
        """The template must be the exit-2 refusal, with its own message."""
        repo = _repo(HERE)
        root = tempfile.mkdtemp(prefix="i2_check09_tpl_")
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__",
                                                      "solutions"))
        try:
            code = ("import sys; sys.path.insert(0, %r)\n"
                    "import configs, stage_09 as s9\n"
                    "try:\n"
                    "    s9.quant_weights(configs.CONFIGS['TINY_MHA'], 'int4')\n"
                    "except NotImplementedError as e:\n"
                    "    assert 'implement' in str(e), e\n"
                    "    print('not implemented yet')\n"
                    "    raise SystemExit(42)\n"
                    "raise SystemExit(7)\n" % (course,))
            proc = subprocess.run([sys.executable, "-c", code],
                                  capture_output=True, text=True, timeout=120)
            if proc.returncode == 42 and "not implemented yet" in proc.stdout:
                return 2, proc.stdout.strip()
            return 1, "template did not raise the stub: %s" % (proc.stderr,)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    ambient = next((p for p in sys.path
                    if os.path.isfile(os.path.join(p, "configs.py"))
                    and os.path.isfile(os.path.join(p, "stage_09.py"))),
                    None)
    if ambient is not None:
        root = None
        course = ambient
    else:
        root = tempfile.mkdtemp(prefix="i2_check09_env_")
        course = os.path.join(root, COURSE)
        _harness_env(root)
        sys.path.insert(0, course)
    try:
        import configs
        import devices
        import stage_01 as s1
        import stage_06 as s6
        import stage_09 as s9

        problems = []
        facts = 0

        def fact(label, ok):
            nonlocal facts
            facts += 1
            if not ok:
                problems.append(label)
                print("  !! %s" % (label,))

        def must(label, ok):
            if not ok:
                raise AssertionError(label)

        tiny = configs.CONFIGS["TINY_MHA"]
        gqa = configs.CONFIGS["SEVEN_GQA"]
        D = devices.DEVICES["D_CLASS"]
        H = devices.DEVICES["H_CLASS"]
        fake = configs.Config("FAKE_MHA", 3, 256, 4, 2, 64, 1024, 8192)
        odd = configs.Config("ODD_TIE", 1, 385, 5, 1, 77, 1, 385)

        stub = 0
        try:
            s9.quant_weights(tiny, "int4")
        except NotImplementedError as error:
            must("stub message", STUB_MESSAGE in str(error))
            stub += 1
        if stub:
            print("check_09: stage 9: not implemented yet (%s)"
                  % (STUB_MESSAGE,))
            raise SystemExit(2)

        # --- the vocabulary
        fact("QUANT_KEYS is the four-line row",
             s9.QUANT_KEYS == ("weights", "kv", "total", "gain_per_mille"))

        # --- quant_weights: stage 1's rules, packing included (§3.9)
        fact("TINY fp16 weights", s9.quant_weights(tiny, "fp16") ==
             31457280)
        must("fp8 and int8 share one number",
             s9.quant_weights(tiny, "fp8") == 15728640
             and s9.quant_weights(tiny, "int8") == 15728640)
        fact("TINY int4 packs (params+1)//2",
             s9.quant_weights(tiny, "int4") == 7864320)
        fact("FAKE int4 packs", s9.quant_weights(fake, "int4") == 2523136)
        # ODD_TIE's qkv, o and head matrices are each ODD: per-matrix
        # rounding lifts four halves, so the pack is 252562 — one-shot
        # packing of the 505120 total would answer 252560
        fact("ODD_TIE int4 is per-matrix, not one-shot",
             s9.quant_weights(odd, "int4") == 252562)

        # --- quant_step: the four-line row, hand-derived (§2)
        must("TINY D fp16 baseline",
             s9.quant_step(tiny, D, 1, 1, "fp16") ==
             {"weights": 31457280, "kv": 18432, "total": 43435,
              "gain_per_mille": 0})
        must("TINY D int8",
             s9.quant_step(tiny, D, 1, 1, "int8") ==
             {"weights": 15728640, "kv": 18432, "total": 26095,
              "gain_per_mille": 399})
        fact("fp8 step == int8 step, two names one number",
             s9.quant_step(tiny, D, 1, 1, "fp8") ==
             s9.quant_step(tiny, D, 1, 1, "int8"))
        must("TINY D int4",
             s9.quant_step(tiny, D, 1, 1, "int4") ==
             {"weights": 7864320, "kv": 18432, "total": 17428,
              "gain_per_mille": 598})
        must("GQA H ctx1024 b8 int8",
             s9.quant_step(gqa, H, 1024, 8, "int8") ==
             {"weights": 5801771008, "kv": 1074790400, "total": 2598085,
              "gain_per_mille": 454})
        # the gain floors: (15561 * 1000) / 10110 = 354.85... — a model
        # that rounds answers 355
        fact("FAKE D int8 gain floors to 354",
             s9.quant_step(fake, D, 1, 1, "int8") ==
             {"weights": 5046272, "kv": 3072, "total": 10110,
              "gain_per_mille": 354})
        fact("ODD_TIE D int4",
             s9.quant_step(odd, D, 1, 1, "int4") ==
             {"weights": 252562, "kv": 616, "total": 2026,
              "gain_per_mille": 291})

        # --- the cache law: fp16 under every weight dtype (§3.7/§3.9)
        fact("the kv line is immune to the pack",
             all(s9.quant_step(tiny, D, 1, 1, dt)["kv"] == 18432
                 for dt in ("fp16", "fp8", "int8", "int4")))
        fact("the kv line grows with batch: GQA int4 ctx1024 b8",
             s9.quant_step(gqa, H, 1024, 8, "int4")["kv"] == 1074790400)

        # --- the total is stage 6's own step at the same dtype (§3.6)
        fact("total is stage 6's decode total",
             s9.quant_step(tiny, H, 1024, 1, "int8")["total"] ==
             s6.decode(tiny, H, "int8", 1024, 1)["total"])

        # --- refusals
        _refuses(s1.PhysError, "quant_weights refuses an invalid config",
                 lambda: s9.quant_weights(
                     configs.Config("BADTILE", 2, 256, 5, 1, 64, 128, 128),
                     "int4"), names=("BADTILE",))
        _refuses(s1.PhysError, "quant_weights refuses an unknown dtype",
                 lambda: s9.quant_weights(tiny, "fp32"), names=("fp32",))
        _refuses(s1.PhysError, "quant_step refuses an invalid config",
                 lambda: s9.quant_step(
                     configs.Config("BADKV", 2, 256, 4, 3, 64, 512, 512),
                     D, 1, 1, "int8"), names=("BADKV",))
        _refuses(s1.PhysError, "quant_step refuses an unknown device",
                 lambda: s9.quant_step(
                     tiny, devices.Device("TINY_ACCEL", 1, 1, 1, 1, 1, 1),
                     1, 1, "int8"), names=("TINY_ACCEL",))
        _refuses(s1.PhysError, "quant_step refuses ctx=0",
                 lambda: s9.quant_step(tiny, D, 0, 1, "int8"),
                 names=("ctx=0", "a step"))
        _refuses(s1.PhysError, "quant_step refuses batch=0",
                 lambda: s9.quant_step(tiny, D, 1, 0, "int8"),
                 names=("batch=0", "a step"))
        _refuses(s1.PhysError, "quant_step refuses an unknown dtype",
                 lambda: s9.quant_step(tiny, D, 1, 1, "fp32"),
                 names=("fp32",))

        if problems:
            raise AssertionError("%d facts failed" % (len(problems),))
        print("check_09: PASS (%d facts)" % (facts,))
        return 0
    finally:
        if root:
            sys.path[:] = [p for p in sys.path if p != course]
            shutil.rmtree(root, ignore_errors=True)

# --- stage 10 ----------------------------------------------------------------------
def check_10():
    import os
    import shutil
    import subprocess
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "transformer-inference-physics"

    STAGE = 10

    STUB_MESSAGE = "stage 10: implement predict()"

    ROWS = (
        (("TINY_MHA", "D_CLASS", "W_A", "fp16"), 404155, 56621, 17661, 11796480),
        (("TINY_MHA", "H_CLASS", "W_A", "fp16"), 64747, 23443, 42656, 11796480),
        (("TINY_MHA", "H_CLASS", "W_F", "fp16"), 234070051, 470323, 2126,
         1208549376),
        (("SEVEN_MHA", "H_CLASS", "W_A", "fp16"), 20083276, 5189811, 192,
         671088640),
        (("SEVEN_MHA", "H_CLASS", "W_B", "fp16"), 89467820, 5790786, 172,
         2281701376),
        (("SEVEN_GQA", "A_CLASS", "W_A", "fp16"), 60188611, 7726639, 129,
         167772160),
        (("SEVEN_GQA", "H_CLASS", "W_A", "fp16"), 17700972, 4419754, 226,
         167772160),
        (("SEVEN_GQA", "H_CLASS", "W_B", "fp16"), 79938604, 4569997, 218,
         570425344),
        (("SEVEN_GQA", "H_CLASS", "W_B", "int8"), 39986145, 2405154, 415,
         570425344),
        (("SEVEN_GQA", "H_CLASS", "W_C", "fp16"), 185156940, 4767192, 209,
         1090519040),
        (("SEVEN_GQA", "H_CLASS", "W_D", "fp16"), 140687308, 4814314, 1661,
         167772160),
        (("SEVEN_GQA", "H_CLASS", "W_E", "fp16"), 562354700, 6167095, 5188,
         167772160),
        (("SEVEN_MQA", "H_CLASS", "W_B", "fp16"), 77159244, 4213918, 237,
         71303168),
        (("SEVEN_MQA", "H_CLASS", "W_D", "int8"), 67581121, 2167263, 3691,
         20971520),
        (("BIG_GQA", "H_CLASS", "W_A", "int8"), 103705889, 26155164, 38,
         419430400),
        (("BIG_GQA", "H_CLASS", "W_B", "int8"), 437228129, 26530772, 37,
         1426063360),
    )

    def _repo(start=None):
        for candidate_start in (os.environ.get("I2_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "configs.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set I2_REPO=/path/to/forja")

    def _harness_env(root):
        """Copy the repo's course into `root` with solutions/ overlaid."""
        repo = _repo(HERE)
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__"))
        overlay = os.path.join(course, "solutions")
        if os.path.isdir(overlay):
            for name in os.listdir(overlay):
                if name.startswith("stage_") and name.endswith(".py"):
                    shutil.copy2(os.path.join(overlay, name),
                                 os.path.join(course, name))

    def _refuses(exc, what, call, names=()):
        """`call()` must raise `exc` naming every string in `names`."""
        try:
            call()
        except exc as problem:
            text = str(problem)
            missing = [w for w in tuple(names) if w not in text]
            if missing:
                raise AssertionError(
                    "%s: refusal %r does not name %s"
                    % (what, text, missing))
        else:
            raise AssertionError("%s: no refusal" % (what,))

    def _template_verdict():
        """The template must be the exit-2 refusal, with its own message."""
        repo = _repo(HERE)
        root = tempfile.mkdtemp(prefix="i2_check10_tpl_")
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course,
                        ignore=shutil.ignore_patterns("__pycache__",
                                                      "solutions"))
        try:
            code = ("import sys; sys.path.insert(0, %r)\n"
                    "import stage_10 as s10\n"
                    "try:\n"
                    "    s10.predict('TINY_MHA', 'D_CLASS', 'W_A', 'fp16')\n"
                    "except NotImplementedError as e:\n"
                    "    assert 'implement' in str(e), e\n"
                    "    print('not implemented yet')\n"
                    "    raise SystemExit(42)\n"
                    "raise SystemExit(7)\n" % (course,))
            proc = subprocess.run([sys.executable, "-c", code],
                                  capture_output=True, text=True, timeout=120)
            if proc.returncode == 42 and "not implemented yet" in proc.stdout:
                return 2, proc.stdout.strip()
            return 1, "template did not raise the stub: %s" % (proc.stderr,)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    ambient = next((p for p in sys.path
                    if os.path.isfile(os.path.join(p, "configs.py"))
                    and os.path.isfile(os.path.join(p, "stage_10.py"))),
                    None)
    if ambient is not None:
        root = None
        course = ambient
    else:
        root = tempfile.mkdtemp(prefix="i2_check10_env_")
        course = os.path.join(root, COURSE)
        _harness_env(root)
        sys.path.insert(0, course)
    try:
        import configs
        import devices
        import trace
        import stage_01 as s1
        import stage_05 as s5
        import stage_10 as s10

        problems = []
        facts = 0

        def fact(label, ok):
            nonlocal facts
            facts += 1
            if not ok:
                problems.append(label)
                print("  !! %s" % (label,))

        def must(label, ok):
            if not ok:
                raise AssertionError(label)

        stub = 0
        try:
            s10.predict("TINY_MHA", "D_CLASS", "W_A", "fp16")
        except NotImplementedError as error:
            must("stub message", STUB_MESSAGE in str(error))
            stub += 1
        if stub:
            print("check_10: stage 10: not implemented yet (%s)"
                  % (STUB_MESSAGE,))
            raise SystemExit(2)

        # --- the vocabulary
        fact("PREDICT_KEYS is the six-number row",
             s10.PREDICT_KEYS == ("ttft_ns", "ttft_bound", "itl_ns",
                                  "itl_bound", "tokens_per_second",
                                  "kv_bytes"))
        fact("PROOF_KEYS is rows, verdict, reasons",
             s10.PROOF_KEYS == ("rows", "verdict", "reasons"))

        # --- the sixteen rows, hand-asserted
        for row, ttft, itl, tps, kv in ROWS:
            pred = s10.predict(*row)
            must("predict %s: %r" % (row, pred),
                 pred["ttft_ns"] == ttft and pred["itl_ns"] == itl
                 and pred["tokens_per_second"] == tps
                 and pred["kv_bytes"] == kv)

        # every TRACKS row: ttft compute-bound, itl memory-bound
        fact("the bounds ride the whole grid",
             all(s10.predict(*row)["ttft_bound"] == "compute"
                 and s10.predict(*row)["itl_bound"] == "memory"
                 for row, _, _, _, _ in ROWS))

        # the probe tax is on BOTH events: the model's prefill is the
        # trace's ttft minus exactly one probe
        tiny = configs.CONFIGS["TINY_MHA"]
        D = devices.DEVICES["D_CLASS"]
        fact("ttft pays one probe on top of prefill",
             s10.predict("TINY_MHA", "D_CLASS", "W_A", "fp16")["ttft_ns"]
             - s5.prefill(tiny, D, "fp16", 1024, 1)["total"]
             == trace.PROBE_NS)

        # tps self-consistency: batch ns per itl, floored
        fact("tps is batch * 1e9 // itl",
             s10.predict("SEVEN_GQA", "H_CLASS", "W_E", "fp16")[
                 "tokens_per_second"]
             == 32 * 1000000000 // 6167095)

        # --- the VRAM walls: refuse before any arithmetic (§3.10)
        _refuses(s1.PhysError, "W_A on BIG fp16 is a wall",
                 lambda: s10.predict("BIG_GQA", "H_CLASS", "W_A", "fp16"),
                 names=("BIG_GQA", "W_A", "wall"))
        _refuses(s1.PhysError, "W_E on 7B-MHA at D is a wall",
                 lambda: s10.predict("SEVEN_MHA", "D_CLASS", "W_E", "fp16"),
                 names=("SEVEN_MHA", "W_E", "wall"))
        # the int8 BIG row the grid does carry must NOT refuse
        fact("BIG int8 W_A serves on the same box",
             s10.predict("BIG_GQA", "H_CLASS", "W_A", "int8")["ttft_ns"]
             == 103705889)

        # --- name refusals
        _refuses(s1.PhysError, "predict refuses an unknown config",
                 lambda: s10.predict("NOPE_MHA", "D_CLASS", "W_A", "fp16"),
                 names=("NOPE_MHA",))
        _refuses(s1.PhysError, "predict refuses an unknown device",
                 lambda: s10.predict("TINY_MHA", "TINY_ACCEL", "W_A",
                                     "fp16"),
                 names=("TINY_ACCEL",))
        _refuses(s1.PhysError, "predict refuses an unknown workload",
                 lambda: s10.predict("TINY_MHA", "D_CLASS", "W_Z", "fp16"),
                 names=("W_Z",))
        _refuses(s1.PhysError, "predict refuses an unknown dtype",
                 lambda: s10.predict("TINY_MHA", "D_CLASS", "W_A", "fp32"),
                 names=("fp32",))

        # --- the honest grid passes (§3.10: equality against the world)
        proof = s10.audit()
        fact("audit grades every TRACKS row",
             len(proof["rows"]) == len(trace.TRACKS))
        fact("the honest grid passes", proof["verdict"] == "pass")
        fact("a pass has no reasons", proof["reasons"] == ())
        fact("audit rows are (row, prediction) pairs",
             proof["rows"][0][0] == tuple(trace.TRACKS[0])
             and proof["rows"][0][1]["ttft_ns"] == 404155)

        # --- a doctored row fails by name
        grid = [(row, dict(s10.predict(*row))) for row in trace.TRACKS]
        grid[3][1]["ttft_ns"] += 1
        proof = s10.audit(grid)
        fact("the doctored grid fails", proof["verdict"] == "fail")
        must("one nanosecond is one reason", len(proof["reasons"]) == 1)
        row, key, expected, got = proof["reasons"][0]
        fact("the reason names the liar",
             row == tuple(trace.TRACKS[3]) and key == "ttft_ns"
             and expected == trace.measure("ttft", *trace.TRACKS[3])
             and got == expected + 1)

        grid2 = [(row, dict(s10.predict(*row))) for row in trace.TRACKS]
        grid2[0][1]["itl_bound"] = "compute"
        proof = s10.audit(grid2)
        must("a flipped bound is one reason too",
             proof["verdict"] == "fail" and len(proof["reasons"]) == 1
             and proof["reasons"][0][1] == "itl_bound")

        grid3 = [(row, dict(s10.predict(*row))) for row in trace.TRACKS]
        grid3[7][1]["tokens_per_second"] += 1
        proof = s10.audit(grid3)
        must("a doctored tps names the key",
             proof["verdict"] == "fail"
             and [r[1] for r in proof["reasons"]]
             == ["tokens_per_second"])

        grid4 = [(row, dict(s10.predict(*row))) for row in trace.TRACKS]
        grid4[15][1]["kv_bytes"] += 1
        proof = s10.audit(grid4)
        must("a doctored kv names the key",
             proof["verdict"] == "fail"
             and [r[1] for r in proof["reasons"]] == ["kv_bytes"])

        if problems:
            raise AssertionError("%d facts failed" % (len(problems),))
        print("check_10: PASS (%d facts)" % (facts,))
        return 0
    finally:
        if root:
            sys.path[:] = [p for p in sys.path if p != course]
            shutil.rmtree(root, ignore_errors=True)

# --- the manifest. One entry per stage, in the order a reader meets them.

STAGES = [
    stage(
        1,
        file="stage_01.py",
        title='The parameters: what a config is',
        tags=['params', 'dtype', 'weights'],
        action="Write `validate`, `count_params` and `weight_bytes` in stage_01.py.",
        predict="Why the addresses must tile the residual stream, and what int4's packing rule costs a model rounded twice.",
        check=check_1,
    ),
    stage(
        2,
        file="stage_02.py",
        title='The flops: the compute budget',
        tags=['flops', 'matmuls', 'prefill'],
        action="Write `flops_token` and `flops_prefill` in stage_02.py.",
        predict="Why only matmuls are flops, why GQA is invisible in the compute line, and why the head runs once per sequence.",
        check=check_2,
    ),
    stage(
        3,
        file="stage_03.py",
        title='The bytes: the memory budget',
        tags=['kv-cache', 'bytes', 'intensity'],
        action="Write `kv_bytes_per_token`, `kv_total`, `bytes_decode`, `bytes_prefill` and `arithmetic_intensity` in stage_03.py.",
        predict="Why the cache a sequence owns is the read every step pays, and what the one intensity number decides.",
        check=check_3,
    ),
    stage(
        4,
        file="stage_04.py",
        title="The roofline: the race's rules",
        tags=['roofline', 'max', 'launch'],
        action="Write `op_time`, `classify`, `ridge`, `ops_decode`, `ops_prefill`, `phase_time` and `phase_bound` in stage_04.py.",
        predict="Why the wall time is the max of two budgets and not their sum, and why a tie serves memory.",
        check=check_4,
    ),
    stage(
        5,
        file="stage_05.py",
        title="Prefill: TTFT's model",
        tags=['prefill', 'ttft', 'compute-bound'],
        action="Write `prefill` in stage_05.py.",
        predict="Why prefill is compute-bound and what the probe tax belongs to, and not to the arithmetic.",
        check=check_5,
    ),
    stage(
        6,
        file="stage_06.py",
        title="Decode: ITL's model",
        tags=['decode', 'itl', 'memory-bound'],
        action="Write `decode` in stage_06.py.",
        predict="Why decode is memory-bound by a hundred-fold and what an empty cache would cost that it cannot cost.",
        check=check_6,
    ),
    stage(
        7,
        file="stage_07.py",
        title='The KV cache: the third budget',
        tags=['kv-cache', 'vram', 'context'],
        action="Write `cache_table`, `cache_life` and `vram_batch_edge` in stage_07.py.",
        predict="Where the cache catches the weights, why MHA dies four contexts sooner, and what an edge of zero sequences means.",
        check=check_7,
    ),
    stage(
        8,
        file="stage_08.py",
        title='The crossover: where decode stops being memory-bound',
        tags=['batching', 'crossover', 'curve'],
        action="Write `crossover_batch` and `batch_curve` in stage_08.py.",
        predict="Why the mlp is the first op to flip and what the curve bends over exactly once.",
        check=check_8,
    ),
    stage(
        9,
        file="stage_09.py",
        title="Quantization: the weights' half of the trade",
        tags=['quantization', 'int4', 'gain'],
        action="Write `quant_weights` and `quant_step` in stage_09.py.",
        predict="Why fp8 and int8 are the same number here and why the KV cache's rent is immune to packing.",
        check=check_9,
    ),
    stage(
        10,
        file="stage_10.py",
        title='The audit: the model meets the measurement',
        tags=['audit', 'trace', 'vram-law'],
        action="Write `predict` and `audit` in stage_10.py.",
        predict="Why one nanosecond is one wrong formula, why the audit re-measures through the world, and where the grid runs into walls.",
        check=check_10,
    ),
]
