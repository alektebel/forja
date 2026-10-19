"""Compression From Scratch — codecs over provided corpora.

Ten graded stages over a world provided as data (`corpus.py`, `inflate.py`,
`lz4ref.py`, `zstdref.py`), the way the rest of this repository teaches a
mechanism: the world is data and holds the ground truth, a stage is a file
you write, a check is what happens to it, and the reference decoders are the
judges — because a byte format you can be exactly wrong about has exactly
one authority.

What the course is about, in one line: *repetition becomes ratios, and
every step of that becoming is a format you have to get right.*

    the bit writer: LSB-first, widths that fit
    run-length: the format that cannot fail
    canonical Huffman: codes from lengths
    the length limit: a code that fits the writer
    LZ77: the window and the matches
    LZ4's block format: nibbles and extensions
    DEFLATE: stored, static, dynamic
    FSE: the table the format builds
    the frame: a header, blocks, and a checksum
    the proof: every codec, every corpus, one verdict

The house laws hold here (`.h7-dev/CONTRACT.md` §1): standard library only,
no `float` literal — a ratio is ints the whole way (`compressed * 1000 //
original` against the world's `BARS`) —, no `random` (the one noise corpus
is a fixed LCG), no clock, no thread, no socket, and no `zlib`/`gzip`/`bz2`
in a stage: the compressed formats are what a student writes, the reference
decoders are what grades it.

What the course does **not** do is shell out: there is no `zlib` behind
`huffman_lengths`, no real filesystem behind a stage's bytes — the corpora
are data, the decoders are strict readers, and the whole course is
deterministic enough that two runs against the same corpus produce the
same bytes.

    python3 codecraft/cli.py run compression-from-scratch
"""

from codecraft.api import stage

TITLE = "Compression From Scratch"
DESCRIPTION = ("Codecs over provided corpora, judged by the ratio and the "
               "reference decoders: ten stages that write bits LSB-first, "
               "mark runs, build canonical Huffman codes from lengths alone, "
               "fit them under a width limit with Kraft's sum back at one, "
               "trade the LZ77 window for matches, write LZ4's nibble "
               "tokens, choose DEFLATE's block mode per block, build FSE's "
               "table, frame it all behind a checksum that notices one "
               "flipped bit, and prove every codec against the world's own "
               "bars — with the ratios ints the whole way.")

LEVEL = "advanced"
ORDER = 36


# --- stage 1 -----------------------------------------------------------------------
def check_1():
    import hashlib
    import os
    import shutil
    import subprocess
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "compression-from-scratch"

    STAGE = 1

    STUB_MESSAGE = "stage 1: implement write_bits()"

    def _repo(start=None):
        for candidate_start in (os.getcwd(), os.environ.get("H7_REPO"), start,
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "corpus.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set H7_REPO=/path/to/learn-stuff-from-scratch")

    def _harness_env(root):
        """Copy the repo's course into `root` with solutions/ overlaid."""
        repo = _repo(HERE)
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course)
        src = os.path.join(repo, "solutions" if os.path.isdir(
            os.path.join(repo, "solutions")) else COURSE)
        overlay = os.path.join(repo, COURSE, "solutions")
        if not os.path.isdir(overlay):
            overlay = os.path.join(repo, COURSE)
        for name in os.listdir(overlay):
            source = os.path.join(overlay, name)
            if os.path.isdir(source):
                continue
            shutil.copy2(source, os.path.join(course, name))

    def _refuses(exc, what, call, names=()):
        """`call()` must raise `exc` naming every string in `names`;
        `what` is the fact's label."""
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

    def _run_course_check(course):
        """The course's own stage check, if the course ships one."""
        return None  # stage 1: the template ships no runner; the verdict is here

    def _run_py(course, snippet):
        """A snippet with the course dir importable: exit code + output."""
        code = ("import sys; sys.path.insert(0, %r)\n"
                % (course,)) + snippet
        proc = subprocess.run([sys.executable, "-c", code],
                              capture_output=True, text=True, timeout=120)
        return proc.returncode, proc.stdout + proc.stderr

    def _template_verdict():
        """The template must be the exit-2 refusal, with its own message."""
        repo = _repo(HERE)
        root = tempfile.mkdtemp(prefix="h7_check01_tpl_")
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course)
        try:
            code = ("import sys; sys.path.insert(0, %r)\n"
                    "import stage_01 as s1\n"
                    "stub = 0\n"
                    "for call in (lambda: s1.BitWriter().append(1, 1),\n"
                    "             lambda: s1.BitWriter().bytes(),\n"
                    "             lambda: s1.write_bits(b'', 0, 1),\n"
                    "             lambda: s1.bit_length_of(1)):\n"
                    "    try:\n"
                    "        call()\n"
                    "    except NotImplementedError as e:\n"
                    "        assert 'implement' in str(e), e\n"
                    "        stub += 1\n"
                    "    except AttributeError:\n"
                    "        stub += 1\n"
                    "if stub == 4:\n"
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
                    if os.path.isfile(os.path.join(p, "corpus.py"))
                    and os.path.isfile(os.path.join(p, "stage_01.py"))), None)
    if ambient is not None:
        root = None  # the ambient tree is the one under test; do not rmtree it
        course = ambient
    else:
        root = tempfile.mkdtemp(prefix="h7_check01_env_")
        course = os.path.join(root, COURSE)
        _harness_env(root)  # copy the repo's course in, solutions overlaid
        sys.path.insert(0, course)
    try:
        import corpus
        import inflate
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

        # --- the world's pins, re-read (the check is not above the world)
        sizes = {"TEXT": 1874, "JSON_LIKE": 8033, "BINARY": 2608,
                 "RANDOM": 1024, "EMPTY": 0}
        for name in corpus.CORPORA:
            data = getattr(corpus, name)
            must("corpus %s is bytes" % (name,), isinstance(data, bytes))
            must("corpus %s size" % (name,), len(data) == sizes[name])
            must("corpus %s sha pinned" % (name,),
                 hashlib.sha256(data).hexdigest() == corpus.digest(name))
        must("bar rle/BINARY=700",
             ("BINARY", "rle", 700) in corpus.BARS)

        # --- the template's surface exists in full; the stub's own
        # refusal is the exit-2 verdict, so probe it before anything
        stub = 0
        for member in ("append", "bytes"):
            if not hasattr(s1.BitWriter, member):
                stub += 1
        for member in ("write_bits", "bit_length_of"):
            if not callable(getattr(s1, member, None)):
                stub += 1
        if stub:
            print("check_01: stage 1: not implemented yet "
                  "(%d of the stage's names are still stubs)"
                  % (stub,))
            raise SystemExit(2)
        must("EncodeError exists", hasattr(s1, "EncodeError")
             and issubclass(s1.EncodeError, ValueError))

        # --- bit_length_of: the width append checks
        must("bit_length_of(0)", s1.bit_length_of(0) == 0)
        must("bit_length_of(1)", s1.bit_length_of(1) == 1)
        must("bit_length_of(255)", s1.bit_length_of(255) == 8)
        must("bit_length_of(256)", s1.bit_length_of(256) == 9)
        must("bit_length_of(2**63 - 1)", s1.bit_length_of(2**63 - 1) == 63)
        _refuses(s1.EncodeError, ("negative n refused", "negative"),
                 lambda: s1.bit_length_of(-1), names=("-1",))

        # --- append/bytes: LSB-first, exactly the reader's order
        w = s1.BitWriter()
        w.append(0b101, 3).append(0b11, 2).append(0b0, 3)
        first = w.bytes()
        fact("LSB-first packing byte", first == b"\x1d")
        reader = inflate.BitReader(first)
        fact("reader reads 0b101 back", reader.read(3) == 0b101)
        fact("reader reads 0b11 back", reader.read(2) == 0b11)
        fact("reader reads the zero back", reader.read(3) == 0)
        fact("reader consumed one byte", reader.pos == 8)

        # the reader's own round-trip over a mixed-width stream
        widths = (1, 3, 2, 7, 5, 4, 8, 6, 9)
        values = tuple((i * 197 + 13) % (1 << width) for i, width in
                       enumerate(widths))
        w = s1.BitWriter()
        for value, width in zip(values, widths):
            w.append(value, width)
        packed = w.bytes()
        reader = inflate.BitReader(packed)
        for value, width in zip(values, widths):
            fact("mixed width %d round-trips" % (width,),
                 reader.read(width) == value)
        fact("mixed stream consumed wholly",
             reader.pos == sum(widths) == len(packed) * 8 - 3)

        # every bit index and every bit of the byte is exercised
        w = s1.BitWriter()
        w.append(0b111, 3).append(0b0, 2).append(0b111, 3)
        fact("all-ones byte", w.bytes() == b"\xe7")

        # the law of the padding: same bits, same bytes, zero-filled tail
        w1 = s1.BitWriter()
        w1.append(1, 1)
        w2 = s1.BitWriter()
        w2.append(1, 1).append(0, 1).append(0, 1)
        must("padding is zeros", w1.bytes() == w2.bytes() == b"\x01")

        # zero-width and zero-value writes still take the bytes owed
        w = s1.BitWriter()
        w.append(0, 0).append(0, 8).append(0, 0)
        fact("zero-width appends hold bytes", w.bytes() == b"\x00")

        # bytes() is a copy: appending after reading never changes the read
        w = s1.BitWriter()
        w.append(0b10, 2)
        first = w.bytes()
        w.append(0b11, 2)
        fact("bytes() snapshot unaffected", first == b"\x02"
             and w.bytes() == b"\x0e")

        # --- the refusal: a value that does not fit its width
        w = s1.BitWriter()
        _refuses(s1.EncodeError, "append over-width refused",
                 lambda: w.append(0b1000, 3), names=("8", "3"))
        _refuses(s1.EncodeError, "append negative refused",
                 lambda: w.append(-1, 3), names=("-1",))
        _refuses(s1.EncodeError, "append width 0 holds nothing",
                 lambda: w.append(1, 0), names=("1", "0"))
        _refuses(s1.EncodeError, "append negative width refused",
                 lambda: w.append(0, -1), names=("-1",))
        fact("refused append left the stream whole", w.bytes() == b"")

        # --- write_bits: the buffer's first `width` bits, overwritten
        # LSB-first, the buffer's length kept.
        out = s1.write_bits(b"\x00\x00", 0b10, 2)
        fact("write_bits lands LSB-first", out == b"\x02\x00")
        reader = inflate.BitReader(out)
        fact("write_bits reads back", reader.read(2) == 0b10)

        # overwrite replaces; the bits past the width are untouched
        out = s1.write_bits(b"\x05", 0b11, 2)     # 101 <- 11 => 111
        fact("write_bits overwrites in place", out == b"\x07")
        out = s1.write_bits(b"\xff", 0b00, 3)     # 11111111 <- 000
        fact("write_bits clears overwritten bits", out == b"\xf8")
        out = s1.write_bits(b"\xaa\xcd", 0b1, 1)
        fact("write_bits keeps the tail bytes", out == b"\xab\xcd")

        # the buffer's length is never changed, never grown
        fact("write_bits keeps the length",
             len(s1.write_bits(b"\x00\x00", 0b1, 9)) == 2)
        _refuses(s1.EncodeError, "write_bits wider than the buffer refused",
                 lambda: s1.write_bits(b"\x00", 0b1, 9),
                 names=("9", "8"))
        _refuses(s1.EncodeError, "write_bits over-width refused",
                 lambda: s1.write_bits(b"\x00\x00", 0b10000, 3),
                 names=("16", "3"))
        _refuses(s1.EncodeError, "write_bits negative value refused",
                 lambda: s1.write_bits(b"\x00\x00", -2, 3), names=("-2",))

        # write_bits and the writer agree bit for bit: the stream the
        # writer packed, rebuilt by overwriting it one byte at a time
        w = s1.BitWriter()
        values8 = tuple((i * 73 + 41) & 0xFF for i in range(5))
        for value in values8:
            w.append(value, 8)
        rebuilt = b"\x00" * len(w.bytes())
        for at, value in enumerate(values8):
            rebuilt = s1.write_bits(rebuilt, value, 8) if at == 0 else \
                rebuilt[:at] + s1.write_bits(rebuilt[at:], value, 8)
        fact("write_bits rebuilds the writer's stream",
             rebuilt == w.bytes())

        # --- the stage's one decision is pinned: BitReader, not bit 7 first
        w = s1.BitWriter()
        w.append(0b1, 1)
        fact("the stream's first bit is the value's low bit",
             w.bytes()[0] & 1 == 1)

        if problems:
            raise AssertionError("%d facts failed" % (len(problems),))
        print("check_01: PASS (%d facts)" % (facts,))
        return 0
    finally:
        if root:
            sys.path[:] = [p for p in sys.path
                           if p not in (course, os.path.join(course,
                                                             "solutions"))]
        if root:
            shutil.rmtree(root, ignore_errors=True)

# --- stage 2 -----------------------------------------------------------------------
def check_2():
    import os
    import shutil
    import subprocess
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    COURSE = "compression-from-scratch"

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.getcwd(), os.environ.get("H7_REPO"), start,
                                os.path.dirname(HERE), DEFAULT_REPO):
            if not candidate_start:
                continue
            here = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(here, COURSE, "corpus.py")):
                    return here
                parent = os.path.dirname(here)
                if parent == here:
                    break
                here = parent
        raise SystemExit("set H7_REPO=/path/to/learn-stuff-from-scratch")

    def _harness_env(root):
        """Copy the repo's course into `root` with solutions/ overlaid."""
        repo = _repo()
        course = os.path.join(repo, COURSE)
        target = os.path.join(root, COURSE)
        shutil.copytree(course, target)
        solutions = os.path.join(course, "solutions")
        if os.path.isdir(solutions):
            shutil.copytree(solutions, target, dirs_exist_ok=True)
        return target

    def _refuses(exc, what, call, names=()):
        """The refusal is an EncodeError (or a named exc), and it says why."""
        if not isinstance(exc, Exception):
            raise AssertionError("%s: expected %s, got no exception" % (what, call))
        if isinstance(exc, NotImplementedError):
            raise AssertionError("%s: not implemented" % what)
        allowed = (EncodeError,) + tuple(names)
        if not isinstance(exc, allowed):
            raise AssertionError("%s: %s raised %s, not an EncodeError: %s"
                                 % (what, call, type(exc).__name__, exc))
        text = str(exc)
        for token in ("rle", "marker", "count", "byte", "offset", "run"):
            if token in text:
                break
        else:
            raise AssertionError("%s: %s's refusal names nothing: %r"
                                 % (what, call, text))

    class EncodeError(ValueError):
        """Mirror of the stage's own refusal type for isinstance checks."""

    def _stub_message(exc):
        """The NotImplementedError's own text, for the template's verdict."""
        text = str(exc)
        if "stage 2" in text or "stage_02" in text or "rle" in text:
            return text
        return text

    def _is_template():
        """The template is detected by the stub's NotImplementedError."""
        import stage_02
        for func in (getattr(stage_02, "rle_encode", None),
                     getattr(stage_02, "rle_decode", None)):
            if func is None:
                return True
            if _raises_not_implemented(func):
                return True
        return False

    def _raises_not_implemented(func):
        try:
            func(b"")
        except NotImplementedError:
            return True
        except Exception:
            return False
        return False

    ambient = next((p for p in sys.path
                    if os.path.isfile(os.path.join(p, "corpus.py"))
                    and os.path.isfile(os.path.join(p, "stage_02.py"))), None)
    if ambient is not None:
        course_dir = ambient
    else:
        root = tempfile.mkdtemp(prefix="h7_check02_env_")
        course_dir = _harness_env(root)
    sys.path.insert(0, course_dir)
    import corpus
    import stage_02
    sys.path.remove(course_dir)
    if hasattr(stage_02, "EncodeError"):
        globals()["EncodeError"] = stage_02.EncodeError


    # §4: assert every constant the stage declares
    for name in ("MARKER", "MIN_RUN_MARKED", "MAX_RUN"):
        if not hasattr(stage_02, name):
            raise AssertionError("stage_02 is missing the constant %s" % name)
    if not hasattr(stage_02, "EncodeError"):
        raise AssertionError("stage_02 must define its own EncodeError")
    if stage_02.MARKER != 0x00:
        raise AssertionError("MARKER must be 0x00, got %r" % (stage_02.MARKER,))
    if not (2 <= stage_02.MIN_RUN_MARKED <= 255):
        raise AssertionError("MIN_RUN_MARKED out of range: %r"
                             % (stage_02.MIN_RUN_MARKED,))
    if not (1 <= stage_02.MAX_RUN <= 255):
        raise AssertionError("MAX_RUN must fit one count byte: %r"
                             % (stage_02.MAX_RUN,))
    EncodeError = stage_02.EncodeError
    rle_encode = stage_02.rle_encode
    rle_decode = stage_02.rle_decode

    # the world's pins
    for name in corpus.CORPORA:
        data = getattr(corpus, name)
        if len(data) != 0:
            import hashlib
            want = hashlib.sha256(data).hexdigest()
            if corpus.digest(name) != want:
                raise AssertionError("corpus %s moved under us" % name)
    bars = dict((c, m) for (c, _codec, m) in corpus.BARS)
    if bars.get("BINARY") != 700:
        raise AssertionError("the BINARY rle bar moved: %r" % (bars,))

    # 1. round-trip on every corpus, exact
    for name in corpus.CORPORA:
        data = getattr(corpus, name)
        if rle_decode(rle_encode(data)) != data:
            raise AssertionError("round-trip failed on %s" % name)

    # 2. determinism: same input, same bytes
    probe = b"abcabc" * 40 + b"\x00" * 17 + bytes(range(64))
    if rle_encode(probe) != rle_encode(probe):
        raise AssertionError("rle_encode is not deterministic")

    # 3. hand-built vectors: the format, byte for byte
    #    a run of 5 'a' is exactly the record 0x00, 5, 'a'
    e = rle_encode(b"aaaaa")
    if e != bytes([0x00, 0x05, 0x61]):
        raise AssertionError("run vector: %r" % (e,))
    if rle_decode(e) != b"aaaaa":
        raise AssertionError("run vector round-trip")
    #    three distinct literals stay literal
    e = rle_encode(b"abc")
    if e != b"abc":
        raise AssertionError("literals must pass through: %r" % (e,))
    #    a run of 2 (below the marked threshold) stays literal where it pays
    e = rle_encode(b"aabb")
    if rle_decode(e) != b"aabb":
        raise AssertionError("short-run round-trip")
    if len(e) != 4:
        raise AssertionError("a run of two should stay two literal bytes: %r"
                             % (e,))
    #    the marker itself is escaped: a lone 0x00 is the record 0x00,1,0x00
    e = rle_encode(b"\x00")
    if e != bytes([0x00, 0x01, 0x00]):
        raise AssertionError("marker escape vector: %r" % (e,))
    if rle_decode(e) != b"\x00":
        raise AssertionError("marker escape round-trip")
    #    a long run splits at the count byte's ceiling
    run_len = stage_02.MAX_RUN + stage_02.MIN_RUN_MARKED
    data = bytes([0x42]) * run_len
    e = rle_encode(data)
    if len(e) != 6:
        raise AssertionError("a %d run must split into two records: %r"
                             % (run_len, e))
    if rle_decode(e) != data:
        raise AssertionError("long-run split round-trip")

    # 4. decode is strict: the truncated and the absurd are refused
    for bad in (b"\x00",
                b"a\x00",
                bytes([0x00, 0x05]),
                bytes([0x00, 0x05, 0x41, 0x00]),
                bytes([0x00, 0x00, 0x41])):
        try:
            rle_decode(bad)
        except Exception as exc:  # noqa: BLE001
            _refuses(exc, "check_02", "rle_decode(%r)" % (bad,))
        else:
            raise AssertionError("rle_decode accepted the malformed %r" % (bad,))

    # 5. the world's bar: BINARY clears 700 per-mille, measured
    data = corpus.BINARY
    compressed = len(rle_encode(data))
    ratio = compressed * 1000 // len(data)
    if ratio >= bars["BINARY"]:
        raise AssertionError("BINARY ratio %d does not clear the bar %d"
                             % (ratio, bars["BINARY"]))

    # 6. the marker tax on noise is bounded: the format cannot explode
    #    past the escape ceiling (2000 per-mille: every byte a 0x00,1,0x00)
    data = corpus.RANDOM
    compressed = len(rle_encode(data))
    if compressed > 2 * len(data):
        raise AssertionError("RANDOM tax exploded: %d > %d"
                             % (compressed, 2 * len(data)))
    if rle_decode(rle_encode(data)) != data:
        raise AssertionError("RANDOM round-trip")
    ratio = compressed * 1000 // len(data)
    if ratio > 2000:
        raise AssertionError("RANDOM ratio %d exceeds the format's ceiling"
                             % (ratio,))

    # 7. bytes in, bytes out
    for name in ("TEXT", "BINARY"):
        if not isinstance(rle_encode(getattr(corpus, name)), bytes):
            raise AssertionError("rle_encode(%s) is not bytes" % name)
        if not isinstance(rle_decode(rle_encode(getattr(corpus, name))),
                          bytes):
            raise AssertionError("rle_decode is not bytes")

    return "check_02: PASS"

# --- stage 3 -----------------------------------------------------------------------
def check_3():
    import hashlib
    import os
    import shutil
    import subprocess
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "compression-from-scratch"

    STAGE = 3

    STUB_MESSAGE = "stage 3: implement huffman_lengths()"

    def _repo(start=None):
        for candidate_start in (os.getcwd(), os.environ.get("H7_REPO"), start,
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "corpus.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set H7_REPO=/path/to/learn-stuff-from-scratch")

    def _harness_env(root):
        """Copy the repo's course into `root` with solutions/ overlaid."""
        repo = _repo(HERE)
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course)
        overlay = os.path.join(repo, COURSE, "solutions")
        if not os.path.isdir(overlay):
            overlay = os.path.join(repo, COURSE)
        for name in os.listdir(overlay):
            source = os.path.join(overlay, name)
            if os.path.isdir(source):
                continue
            shutil.copy2(source, os.path.join(course, name))

    def _refuses(exc, what, call, names=()):
        """`call()` must raise `exc` naming every string in `names`;
        `what` is the fact's label."""
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

    def _run_py(course, snippet):
        """A snippet with the course dir importable: exit code + output."""
        code = ("import sys; sys.path.insert(0, %r)\n"
                % (course,)) + snippet
        proc = subprocess.run([sys.executable, "-c", code],
                              capture_output=True, text=True, timeout=120)
        return proc.returncode, proc.stdout + proc.stderr

    def _kraft_ok(lengths, limit=15):
        """Kraft's sum as integers: at most one (False = the law is broken)."""
        used = 0
        scale = 1 << limit
        for width in lengths:
            if width:
                if width > limit:
                    return False
                used += scale >> width
        return used <= scale

    def _counts_of(data):
        counts = [0] * 256
        for byte in data:
            counts[byte] += 1
        return counts

    def _reverse_bits(value, width):
        out = 0
        for bit in range(width):
            if (value >> bit) & 1:
                out |= 1 << (width - 1 - bit)
        return out

    def _template_verdict():
        """The template must be the exit-2 refusal, with its own message."""
        repo = _repo(HERE)
        root = tempfile.mkdtemp(prefix="h7_check03_tpl_")
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course)
        try:
            code = ("import sys; sys.path.insert(0, %r)\n"
                    "import stage_03 as s3\n"
                    "stub = 0\n"
                    "for call in (lambda: s3.huffman_lengths(b''),\n"
                    "             lambda: s3.canonical_codes((0,)*256),\n"
                    "             lambda: s3.huffman_encode(b''),\n"
                    "             lambda: s3.huffman_decode(b'', (0,)*256, 0)):\n"
                    "    try:\n"
                    "        call()\n"
                    "    except NotImplementedError as e:\n"
                    "        assert 'implement' in str(e), e\n"
                    "        stub += 1\n"
                    "    except AttributeError:\n"
                    "        stub += 1\n"
                    "if stub == 4:\n"
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
                    if os.path.isfile(os.path.join(p, "corpus.py"))
                    and os.path.isfile(os.path.join(p, "stage_01.py"))), None)
    if ambient is not None:
        root = None  # the ambient tree is the one under test; do not rmtree it
        course = ambient
    else:
        root = tempfile.mkdtemp(prefix="h7_check03_env_")
        course = os.path.join(root, COURSE)
        _harness_env(root)  # copy the repo's course in, solutions overlaid
        sys.path.insert(0, course)
    try:
        import corpus
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

        # --- the world's pins, re-read (the check is not above the world)
        sizes = {"TEXT": 1874, "JSON_LIKE": 8033, "BINARY": 2608,
                 "RANDOM": 1024, "EMPTY": 0}
        for name in corpus.CORPORA:
            data = getattr(corpus, name)
            must("corpus %s is bytes" % (name,), isinstance(data, bytes))
            must("corpus %s size" % (name,), len(data) == sizes[name])
            must("corpus %s sha pinned" % (name,),
                 hashlib.sha256(data).hexdigest() == corpus.digest(name))

        # --- the template's surface exists in full; the stub's own
        # refusal is the exit-2 verdict, so probe it before anything
        stub = 0
        for member in ("huffman_lengths", "canonical_codes",
                       "huffman_encode", "huffman_decode"):
            if not callable(getattr(s3, member, None)):
                stub += 1
        if not hasattr(s3, "EncodeError"):
            stub += 1
        if stub:
            print("check_03: stage 3: not implemented yet "
                  "(%d of the stage's names are still stubs)"
                  % (stub,))
            raise SystemExit(2)

        # --- huffman_lengths: the shape, the frequencies' due
        lengths = s3.huffman_lengths(b"")
        fact("EMPTY gives all-zero lengths",
             lengths == (0,) * 256 and isinstance(lengths, tuple))
        lengths = s3.huffman_lengths(b"\x07")
        fact("one symbol gets width 1",
             lengths == (0,) * 7 + (1,) + (0,) * 248)
        lengths = s3.huffman_lengths(b"\x00\x00\x00\x01")
        fact("two symbols split 1/1",
             lengths[0] == 1 and lengths[1] == 1
             and sum(lengths) == 2)
        lengths = s3.huffman_lengths(b"aab")
        # a: 2, b: 1 — two leaves, so the tree gives both width 1
        fact("aab: two symbols, both width 1",
             lengths[ord('a')] == 1 and lengths[ord('b')] == 1
             and sum(lengths) == 2)
        lengths = s3.huffman_lengths(b"aabcc")
        # the tree's ties break by symbol ascending: 'c' (2) pairs with
        # 'a' (2) before 'b' (1) pairs anything — 'c' keeps width 1
        fact("aabcc: ties break by symbol ascending",
             lengths[ord('a')] == 2 and lengths[ord('b')] == 2
             and lengths[ord('c')] == 1)
        lengths = s3.huffman_lengths(b"\x00\x01\x02")
        # three symbols, all counted 1: the ties must break by symbol
        # ascending — 0 and 1 pair first, 2 joins at the root
        fact("abc: ties break by symbol ascending",
             lengths[0] == 2 and lengths[1] == 2 and lengths[2] == 1)
        lengths = s3.huffman_lengths(corpus.TEXT)
        fact("lengths is a 256-tuple of ints",
             isinstance(lengths, tuple) and len(lengths) == 256
             and all(isinstance(width, int) for width in lengths))
        fact("TEXT lengths: only used symbols coded",
             all(width == 0 or count > 0
                 for width, count in
                 zip(lengths, _counts_of(corpus.TEXT))))
        fact("TEXT lengths: Kraft's sum <= one", _kraft_ok(lengths))
        fact("TEXT lengths: rarer symbol never shorter than frequent",
             lengths[ord('e')] <= lengths[ord('q')])
        for name in ("JSON_LIKE", "BINARY", "RANDOM"):
            fact("%s lengths Kraft ok" % (name,),
                 _kraft_ok(s3.huffman_lengths(getattr(corpus, name))))
        # determinism: same input, same lengths
        fact("huffman_lengths deterministic",
             s3.huffman_lengths(corpus.TEXT)
             == s3.huffman_lengths(corpus.TEXT))

        # a hand-pinned complete code: one width-1 code, two width-2
        lengths = [0] * 256
        lengths[3] = 2
        lengths[4] = 2
        lengths[9] = 1
        codes = s3.canonical_codes(tuple(lengths))
        fact("width-1 symbol takes code 0",
             codes[9] == (0, 1))
        fact("width-2 codes follow at (0+1)<<1",
             codes[3] == (2, 2) and codes[4] == (3, 2))
        # the canonical law itself: by width then symbol, each one past
        lengths = s3.huffman_lengths(corpus.TEXT)
        codes = s3.canonical_codes(lengths)
        fact("codes is a 256-tuple",
             isinstance(codes, tuple) and len(codes) == 256)
        ordered = sorted((width, symbol, code)
                         for symbol, (code, width) in enumerate(codes)
                         if width)
        fact("codes ordered by width then symbol",
             ordered == sorted(ordered, key=lambda row: (row[0], row[1])))
        prev_width, prev_code = 0, -1
        sequential = True
        for width, symbol, code in ordered:
            if width != prev_width:
                # a new width resumes one past the last code, doubled
                # once per extra width of depth
                if code != (prev_code + 1) << (width - prev_width):
                    sequential = False
            elif code != prev_code + 1:
                sequential = False
            prev_width, prev_code = width, code
        fact("each code one past its predecessor", sequential)
        fact("no code overflows its width",
             all(code < (1 << width) for code, width in codes if width))
        fact("canonical codes deterministic",
             s3.canonical_codes(lengths) == codes)

        # Kraft's refusal: widths that over-subscribe the code space
        over = [0] * 256
        over[0] = over[1] = over[2] = over[3] = 1   # four width-1 codes
        _refuses(s3.EncodeError, "Kraft above one refused",
                 lambda: s3.canonical_codes(tuple(over)),
                 names=("Kraft",))

        # --- huffman_encode: the stream and the lengths
        blob, lengths = s3.huffman_encode(b"")
        fact("EMPTY encodes to empty bytes and zero lengths",
             blob == b"" and lengths == (0,) * 256)
        blob, lengths = s3.huffman_encode(b"\x2a")
        fact("one symbol encodes to one bit (one byte)",
             len(blob) == 1)
        # the writer's own law: the bits land LSB-first through BitWriter
        blob, lengths = s3.huffman_encode(b"aab")
        writer = s1.BitWriter()
        codes = s3.canonical_codes(lengths)
        for byte in b"aab":
            code, width = codes[byte]
            writer.append(_reverse_bits(code, width), width)
        fact("encode agrees with BitWriter on the codes",
             blob == writer.bytes())

        # --- huffman_decode: the round-trip, every corpus
        for name in corpus.CORPORA:
            data = getattr(corpus, name)
            blob, lengths = s3.huffman_encode(data)
            back = s3.huffman_decode(blob, lengths, len(data))
            fact("%s round-trips through the stage's own codec"
                 % (name,), back == data)
        # a size below the truth reads a prefix; the stream is exact
        blob, lengths = s3.huffman_encode(corpus.TEXT)
        fact("decode honors the size asked",
             s3.huffman_decode(blob, lengths, 10) == corpus.TEXT[:10])
        # a size the stream cannot feed is a refusal
        _refuses(s3.EncodeError, "stream too short for the size refused",
                 lambda: s3.huffman_decode(blob, lengths, len(corpus.TEXT)
                                           + 1),
                 names=("1874", "1875"))

        # a code that runs past a leaf: an incomplete table whose tree
        # has no path '11' — the bits walk off past the widest code
        # a code that runs past a leaf: an incomplete table (Kraft
        # three quarters) whose tree has no path '11' — the bits walk
        # off past the widest code and the decoder refuses
        stub_lengths = [0] * 256
        stub_lengths[0] = 1   # code 0
        stub_lengths[1] = 2   # code '10'
        _refuses(s3.EncodeError, "a code past a leaf is refused",
                 lambda: s3.huffman_decode(b"\x03",
                                           tuple(stub_lengths), 1),
                 names=("leaf",))
        _refuses(s3.EncodeError, "negative size refused",
                 lambda: s3.huffman_decode(blob, lengths, -1),
                 names=("-1",))

        # the decode is the inverse of THIS encoding, not any: a wrong
        # lengths table decodes to a wrong answer or refuses, never the
        # original
        other = s3.huffman_lengths(corpus.JSON_LIKE)
        try:
            wrong = s3.huffman_decode(blob, other, len(corpus.TEXT))
            fact("wrong lengths never rebuild TEXT", wrong != corpus.TEXT)
        except s3.EncodeError:
            fact("wrong lengths may also refuse", True)

        # determinism: same input, same bytes
        fact("encode deterministic",
             s3.huffman_encode(corpus.TEXT)
             == s3.huffman_encode(corpus.TEXT))

        # the ratio is measured, never asserted: Huffman beats stored
        # on the compressible corpora and never grows RANDOM by much
        blob, _ = s3.huffman_encode(corpus.TEXT)
        fact("TEXT ratio is measured under 700 per mille",
             len(blob) * 1000 // len(corpus.TEXT) < 700)
        blob, _ = s3.huffman_encode(corpus.RANDOM)
        fact("RANDOM stays near its size",
             len(blob) * 1000 // len(corpus.RANDOM) < 1000)

        if problems:
            raise AssertionError("%d facts failed" % (len(problems),))
        print("check_03: PASS (%d facts)" % (facts,))
        return 0
    finally:
        if root:
            sys.path[:] = [p for p in sys.path
                           if p not in (course, os.path.join(course,
                                                             "solutions"))]
        if root:
            shutil.rmtree(root, ignore_errors=True)

# --- stage 4 -----------------------------------------------------------------------
def check_4():
    import os
    import shutil
    import subprocess
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "compression-from-scratch"

    STAGE = 4

    STUB_MESSAGE = "stage 4: implement limit_lengths()"

    def _repo(start=None):
        for candidate_start in (os.getcwd(), os.environ.get("H7_REPO"), start,
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "corpus.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set H7_REPO=/path/to/learn-stuff-from-scratch")

    def _harness_env(root):
        """Copy the repo's course into `root` with solutions/ overlaid."""
        repo = _repo(HERE)
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course)
        overlay = os.path.join(repo, COURSE, "solutions")
        if not os.path.isdir(overlay):
            overlay = os.path.join(repo, COURSE)
        for name in os.listdir(overlay):
            source = os.path.join(overlay, name)
            if os.path.isdir(source):
                continue
            shutil.copy2(source, os.path.join(course, name))

    def _refuses(exc, what, call, names=()):
        try:
            call()
        except exc as problem:
            text = str(problem)
            missing = [w for w in tuple(names) if w not in text]
            if missing:
                raise AssertionError(
                    "%s: refusal %r does not name %s" % (what, text, missing))
        else:
            raise AssertionError("%s: no refusal" % (what,))

    def _run_py(course, snippet):
        code = ("import sys; sys.path.insert(0, %r)\n"
                % (course,)) + snippet
        proc = subprocess.run([sys.executable, "-c", code],
                              capture_output=True, text=True, timeout=120)
        return proc.returncode, proc.stdout + proc.stderr

    def _template_verdict():
        """The template must be the exit-2 refusal, with its own message."""
        repo = _repo(HERE)
        root = tempfile.mkdtemp(prefix="h7_tmpl04_")
        course = os.path.join(root, COURSE)
        try:
            shutil.copytree(os.path.join(repo, COURSE), course)
            code, out = _run_py(course, "import stage_04\n")
            if code == 2 and STUB_MESSAGE.split(": ")[-1] in out:
                return 2
            return 1
        finally:
            shutil.rmtree(root, ignore_errors=True)

    ambient = next((p for p in sys.path
                    if os.path.isfile(os.path.join(p, "corpus.py"))
                    and os.path.isfile(os.path.join(p, "stage_01.py"))), None)
    if ambient is not None:
        root = None  # the ambient tree is the one under test; do not rmtree it
        course = ambient
    else:
        root = tempfile.mkdtemp(prefix="h7_check04_env_")
        course = os.path.join(root, COURSE)
        _harness_env(root)  # copy the repo's course in, solutions overlaid
        sys.path.insert(0, course)
    try:
        import corpus
        import stage_01 as s1
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

        # the world's pins, re-read
        must("bar huffman/TEXT=650", ("TEXT", "huffman", 650) in corpus.BARS)

        # the template's surface: the stub's own refusal is exit 2
        try:
            s4.limit_lengths(tuple([0] * 256), 15)
        except NotImplementedError as stub:
            print("check_04: stage 4: not implemented yet (%s)" % (stub,))
            raise SystemExit(2)
        except Exception:
            pass  # a real refusal from a real implementation: carry on
        must("EncodeError exists", hasattr(s4, "EncodeError")
             and issubclass(s4.EncodeError, ValueError))

        def encode_with(data, lengths):
            codes = s3.canonical_codes(lengths)
            writer = s1.BitWriter()
            for byte in data:
                code, width = codes[byte]
                reversed_code = 0
                for i in range(width):
                    reversed_code = (reversed_code << 1) | ((code >> i) & 1)
                writer.append(reversed_code, width)
            return writer.bytes()

        def kraft_ok(lengths):
            live = [w for w in lengths if w]
            if not live:
                return True
            top = max(live)
            used = sum(1 << (top - w) for w in live)
            return used == (1 << top)

        # --- the shape of the answer, hand-built
        # a trivial code already under the limit passes through whole
        base = [0] * 256
        base[0], base[1] = 1, 2
        for symbol in range(2, 4):
            base[symbol] = 3
        fact("an already-limited code is unchanged",
             s4.limit_lengths(tuple(base), 3) == tuple(base))
        fact("a wider limit leaves a fitting code unchanged",
             s4.limit_lengths(tuple(base), 9) == tuple(base))

        # the one-symbol code: width 1, the only complete code
        one = [0] * 256
        one[7] = 5
        fact("one symbol holds width 1",
             s4.limit_lengths(tuple(one), 15)[7] == 1)
        fact("one symbol holds width 1 tightly",
             s4.limit_lengths(tuple(one), 1)[7] == 1)

        # a code over the limit: every width comes down, Kraft returns
        deep = [0] * 256
        deep[0], deep[1], deep[2] = 1, 2, 3
        deep[3] = 4
        deep[4], deep[5] = 5, 5

        limited = s4.limit_lengths(tuple(deep), 4)
        fact("demotion caps every width", max(limited) <= 4)
        fact("demotion keeps Kraft at one", kraft_ok(limited))
        fact("the frequent symbols keep the shortest widths",
             limited[0] <= min(limited[s] for s in range(1, 6) if limited[s]))

        # --- the corpora: cap, Kraft equality, round-trip through stage 3
        for name in corpus.CORPORA:
            data = getattr(corpus, name)
            lengths = s3.huffman_lengths(data)
            live = sum(1 for w in lengths if w)
            for max_width in (8, 15):
                if live > (1 << max_width):
                    continue
                lim = s4.limit_lengths(lengths, max_width)
                fact("%s at width %d: every width fits" % (name, max_width),
                     max(lim, default=0) <= max_width)
                fact("%s at width %d: Kraft exactly one" % (name, max_width),
                     kraft_ok(lim))
                fact("%s at width %d: no symbol lost" % (name, max_width),
                     sum(1 for w in lim if w) == live)
                if not live:
                    continue
                stream = encode_with(data, lim)
                back = s3.huffman_decode(stream, lim, len(data))
                fact("%s at width %d round-trips" % (name, max_width),
                     back == data)

        # the cost law, measured: limiting never shortens the frequent
        # symbols' codes at the rares' expense beyond the optimum's room
        text_lengths = s3.huffman_lengths(corpus.TEXT)
        lim15 = s4.limit_lengths(text_lengths, 15)
        fact("width 15 leaves the optimum alone (cost in bytes)",
             len(encode_with(corpus.TEXT, lim15))
             <= len(encode_with(corpus.TEXT, text_lengths)))
        lim6 = s4.limit_lengths(text_lengths, 6)
        fact("width 6 costs more than width 15 (the limit's own tax)",
             len(encode_with(corpus.TEXT, lim6))
             >= len(encode_with(corpus.TEXT, lim15)))

        # --- the refusals: a caller's mistake names the offender
        _refuses(s4.EncodeError, "max_width 0 refused",
                 lambda: s4.limit_lengths(text_lengths, 0), names=("0",))
        _refuses(s4.EncodeError, "negative max_width refused",
                 lambda: s4.limit_lengths(text_lengths, -3), names=("-3",))
        _refuses(s4.EncodeError, "a length too small a max_width refuses",
                 lambda: s4.limit_lengths(text_lengths, 1), names=("1",))
        _refuses(s4.EncodeError, "max_width 0 on any lengths refused",
                 lambda: s4.limit_lengths(tuple([0] * 256), 0),
                 names=("0",))
        _refuses(s4.EncodeError, "negative length refused",
                 lambda: s4.limit_lengths(tuple(base[:255]) + (-1,), 8),
                 names=("-1",))
        rand_lengths = s3.huffman_lengths(corpus.RANDOM)
        _refuses(s4.EncodeError, "RANDOM's 254 symbols at width 7 refused",
                 lambda: s4.limit_lengths(rand_lengths, 7),
                 names=("7",))
        over = [0] * 256
        over[0], over[1] = 1, 1
        over[2] = 1
        _refuses(s4.EncodeError, "Kraft above one refused",
                 lambda: s4.limit_lengths(tuple(over), 8),
                 names=("Kraft",))

        if problems:
            raise AssertionError("%d facts failed" % (len(problems),))
        print("check_04: PASS (%d facts)" % (facts,))
        return 0
    finally:
        if root:
            sys.path[:] = [p for p in sys.path
                           if p not in (course,
                                        os.path.join(course, "solutions"))]
        if root:
            shutil.rmtree(root, ignore_errors=True)

# --- stage 5 -----------------------------------------------------------------------
def check_5():
    import os
    import sys
    import shutil
    import subprocess
    import hashlib
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "compression-from-scratch"

    STAGE = 5

    STUB_MESSAGE = "stage 5: implement lz77_encode()"

    def _repo(start=None):
        for candidate_start in (os.getcwd(), os.environ.get("H7_REPO"), start,
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "corpus.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set H7_REPO=/path/to/learn-stuff-from-scratch")

    def _harness_env(root):
        """Copy the repo's course into `root` with solutions/ overlaid."""
        repo = _repo(HERE)
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course)
        overlay = os.path.join(repo, COURSE, "solutions")
        if not os.path.isdir(overlay):
            overlay = os.path.join(repo, COURSE)
        for name in os.listdir(overlay):
            source = os.path.join(overlay, name)
            if os.path.isdir(source):
                continue
            shutil.copy2(source, os.path.join(course, name))

    def _refuses(exc, what, call, names=()):
        """`call()` must raise `exc` naming every string in `names`;
        `what` is the fact's label."""
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

    def _run_py(course, snippet):
        """A snippet with the course dir importable: exit code + output."""
        code = ("import sys; sys.path.insert(0, %r)\n"
                % (course,)) + snippet
        proc = subprocess.run([sys.executable, "-c", code],
                              capture_output=True, text=True, timeout=120)
        return proc.returncode, proc.stdout + proc.stderr

    def _template_verdict():
        """The template must be the exit-2 refusal, with its own message."""
        repo = _repo(HERE)
        root = tempfile.mkdtemp(prefix="h7_check05_tpl_")
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course)
        try:
            code = ("import sys; sys.path.insert(0, %r)\n"
                    "import stage_05 as s5\n"
                    "stub = 0\n"
                    "for call in (lambda: s5.lz77_encode(b'abc', 8, 3, 8),\n"
                    "             lambda: s5.lz77_decode(((3, 1),))):\n"
                    "    try:\n"
                    "        call()\n"
                    "    except NotImplementedError as e:\n"
                    "        assert 'implement' in str(e), e\n"
                    "        stub += 1\n"
                    "    except AttributeError:\n"
                    "        stub += 1\n"
                    "if stub == 2:\n"
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
                    if os.path.isfile(os.path.join(p, "corpus.py"))
                    and os.path.isfile(os.path.join(p, "stage_01.py"))), None)
    if ambient is not None:
        root = None  # the ambient tree is the one under test; do not rmtree it
        course = ambient
    else:
        root = tempfile.mkdtemp(prefix="h7_check05_env_")
        course = os.path.join(root, COURSE)
        _harness_env(root)  # copy the repo's course in, solutions overlaid
        sys.path.insert(0, course)
    try:
        import corpus
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

        # --- the world's pins, re-read (the check is not above the world)
        sizes = {"TEXT": 1874, "JSON_LIKE": 8033, "BINARY": 2608,
                 "RANDOM": 1024, "EMPTY": 0}
        for name in corpus.CORPORA:
            data = getattr(corpus, name)
            must("corpus %s is bytes" % (name,), isinstance(data, bytes))
            must("corpus %s size" % (name,), len(data) == sizes[name])
            must("corpus %s sha pinned" % (name,),
                 hashlib.sha256(data).hexdigest() == corpus.digest(name))

        # --- the template's surface exists in full; the stub's own
        # refusal is the exit-2 verdict, so probe it before anything
        stub = 0
        try:
            s5.lz77_encode(b"abc", 8, 3, 8)
        except NotImplementedError:
            stub += 1
        except s5.EncodeError:
            pass
        try:
            s5.lz77_decode(())
        except NotImplementedError:
            stub += 1
        except s5.EncodeError:
            pass
        if stub:
            print("check_05: stage 5: not implemented yet "
                  "(%d of the stage's names are still stubs)"
                  % (stub,))
            raise SystemExit(2)
        must("EncodeError exists", hasattr(s5, "EncodeError")
             and issubclass(s5.EncodeError, ValueError))

        # --- the stream shape: literals are ints, pairs are (len, dist)
        pairs = s5.lz77_encode(b"ab", 8, 3, 8)
        fact("no match under min_match: all literals",
             pairs == (97, 98))
        pairs = s5.lz77_encode(b"abcabcabc", 8, 3, 8)
        fact("a match is a (length, distance) tuple",
             isinstance(pairs[-1], tuple) and len(pairs[-1]) == 2)
        fact("literals are ints in the stream",
             isinstance(pairs[0], int))
        fact("the encoder's own stream decodes",
             s5.lz77_decode(pairs) == b"abcabcabc")

        # --- the greedy match: the longest the window holds; the copy
        # stops at the data's end (9 a's: literal, then 8 copied)
        fact("a run is a literal then one pair",
             s5.lz77_encode(b"aaaa", 8, 2, 8) == (97, (3, 1)))
        fact("overlapping period-2 run is a pair at distance 2",
             s5.lz77_encode(b"abababab", 8, 2, 8) == (97, 98, (6, 2)))
        fact("period-3 repeat is one pair at distance 3",
             s5.lz77_encode(b"abcabcabc", 8, 3, 8)
             == (97, 98, 99, (6, 3)))

        # --- ties: two candidates of equal length — the nearest wins.
        # At i=7 of b"abcZabcabc", b"abc" matches at distance 3 and
        # distance 7; the stream must carry the distance-3 pair.
        data = b"abc" + b"Z" + b"abc" + b"abc"
        pairs = s5.lz77_encode(data, 16, 3, 8)
        fact("tie goes to the smaller distance",
             pairs == (97, 98, 99, 90, (3, 4), (3, 3)))
        fact("tie's stream still decodes",
             s5.lz77_decode(pairs) == data)
        # --- the window's law: no pair reaches past it, and a window
        # that cannot see the repeat answers literals instead.
        # 16 bytes: b"abcdefghabcdefgh" — the tail matches at distance 8,
        # inside a window of 8, unreachable at a window of 4.
        repeat = b"abcd" + b"efgh" + b"abcd" + b"efgh"
        pairs = s5.lz77_encode(repeat, 8, 4, 8)
        fact("window-8 stream pinned",
             pairs == (97, 98, 99, 100, 101, 102, 103, 104, (8, 8)))
        far = max((item[1] for item in pairs if isinstance(item, tuple)),
                  default=0)
        fact("no distance beyond the window", far <= 8)
        pairs = s5.lz77_encode(repeat, 4, 4, 8)
        fact("repeat past the window is not a pair",
             pairs == (97, 98, 99, 100, 101, 102, 103, 104,
                       97, 98, 99, 100, 101, 102, 103, 104))
        fact("the narrowed window still decodes",
             s5.lz77_decode(pairs) == repeat)

        # --- max_match caps the pair's length; the remainder is
        # literals or later pairs, and the stream still decodes
        data = b"aaaaaaaaaa"
        pairs = s5.lz77_encode(data, 8, 2, 4)
        fact("max_match caps the length, pinned",
             pairs == (97, (4, 1), (4, 1), 97))
        for item in pairs:
            if isinstance(item, tuple):
                fact("no length past max_match", item[0] <= 4)
        fact("capped stream decodes", s5.lz77_decode(pairs) == data)

        # --- the decoder's overlap law: length > distance copies byte
        # by byte, the format repeating itself
        fact("length 999 at distance 1 is a run",
             s5.lz77_decode((97, (999, 1))) == b"a" * 1000)
        # out = abc; copy 7 from distance 3 byte by byte:
        # a b c a b c a b c a — ten bytes, three past the source
        fact("overlap byte-by-byte, not slice",
             s5.lz77_decode((97, 98, 99, (7, 3))) == b"abcabcabca")
        # a slice-based copy would answer b"abc" + 7 stale bytes or
        # refuse; byte-by-byte is the semantics
        fact("overlap starts from the stream's own tail",
             s5.lz77_decode((97, 98, 99, 100, (7, 3)))
             == b"abcdbcdbcdb")

        # --- the order IS the data: interleaved literals and pairs
        # decode positionally
        stream = (104, 101, (3, 2), 108, (2, 1))
        fact("interleaved stream decodes in order",
             s5.lz77_decode(stream) == b"hehehlll")
        fact("pair before literal is not literal before pair",
             s5.lz77_decode((97, (2, 1))) == b"aaa"
             and s5.lz77_decode((97, 97, (2, 1))) == b"aaaa"
             and s5.lz77_decode((97, (2, 1)))
             != s5.lz77_decode((97, 97, (2, 1))))
        # --- EMPTY: the empty stream, both halves
        fact("empty encodes to the empty stream",
             s5.lz77_encode(b"", 8, 3, 8) == ())
        fact("empty stream decodes to empty",
             s5.lz77_decode(()) == b"")

        # --- the encoder's refusals: a caller's mistake, named.
        # The refusals come before the data is touched, so they hold
        # on every corpus, EMPTY included.
        for empty in (b"", corpus.EMPTY):
            _refuses(s5.EncodeError, "window 0 refused",
                     lambda e=empty: s5.lz77_encode(e, 0, 3, 8),
                     names=("0",))
            _refuses(s5.EncodeError, "negative window refused",
                     lambda e=empty: s5.lz77_encode(e, -4, 3, 8),
                     names=("-4",))
            _refuses(s5.EncodeError, "min_match 1 refused (cannot pay)",
                     lambda e=empty: s5.lz77_encode(e, 8, 1, 8),
                     names=("1",))
            _refuses(s5.EncodeError, "max_match below min_match refused",
                     lambda e=empty: s5.lz77_encode(e, 8, 4, 3),
                     names=("4", "3"))

        # --- the decoder's refusals: what the format forbids, named
        _refuses(s5.EncodeError, "distance 0 refused",
                 lambda: s5.lz77_decode(((3, 0),)), names=("0",))
        _refuses(s5.EncodeError, "negative distance refused",
                 lambda: s5.lz77_decode(((3, -2),)), names=("-2",))
        _refuses(s5.EncodeError, "distance past the stream refused",
                 lambda: s5.lz77_decode((97, (3, 4))), names=("4", "1"))
        _refuses(s5.EncodeError, "length 0 refused",
                 lambda: s5.lz77_decode((97, 98, (0, 1))),
                 names=("0",))
        _refuses(s5.EncodeError, "negative length refused",
                 lambda: s5.lz77_decode((97, 98, (-1, 1))),
                 names=("-1",))
        _refuses(s5.EncodeError, "literal over 255 refused",
                 lambda: s5.lz77_decode((256,)), names=("256",))
        _refuses(s5.EncodeError, "negative literal refused",
                 lambda: s5.lz77_decode((-1,)), names=("-1",))
        _refuses(s5.EncodeError, "a junk item refused",
                 lambda: s5.lz77_decode((b"junk",)), names=("junk",))
        _refuses(s5.EncodeError, "a 3-tuple is not a pair",
                 lambda: s5.lz77_decode(((1, 2, 3),)), names=("1", "2", "3"))

        # --- the decoder is strict about non-int fields
        _refuses(s5.EncodeError, "a float length refused",
                 lambda: s5.lz77_decode(((3.0, 1),)), names=("3.0",))

        # --- determinism: the same input, the same stream
        fact("encoding is deterministic",
             s5.lz77_encode(corpus.TEXT, 256, 3, 255)
             == s5.lz77_encode(corpus.TEXT, 256, 3, 255))

        # --- the ratio trade, the stage's whole lesson: the cost model
        # is a literal one byte, a pair three (length + 2-byte distance)
        def cost(stream):
            return sum(1 if isinstance(item, int) else 3
                       for item in stream)

        trade_wins = 0
        for name in ("TEXT", "JSON_LIKE", "BINARY"):
            data = getattr(corpus, name)
            small = s5.lz77_encode(data, 256, 3, 255)
            big = s5.lz77_encode(data, 4096, 3, 255)
            small_cost = cost(small)
            big_cost = cost(big)
            fact("%s: big window never costs more" % (name,),
                 big_cost <= small_cost)
            if big_cost < small_cost:
                trade_wins += 1
            fact("%s: big window decodes" % (name,),
                 s5.lz77_decode(big) == data)
            fact("%s: small window decodes" % (name,),
                 s5.lz77_decode(small) == data)
            small_permille = small_cost * 1000 // len(data)
            big_permille = big_cost * 1000 // len(data)
            print("  ratio %s: window 256 = %d per-mille, "
                  "window 4096 = %d per-mille"
                  % (name, small_permille, big_permille))
        must("the trade shows on the compressible corpora",
             trade_wins >= 2)

        # RANDOM: incompressible, every item a literal, cost 1000 per-mille
        random_stream = s5.lz77_encode(corpus.RANDOM, 4096, 3, 255)
        fact("RANDOM is all literals",
             all(isinstance(item, int) for item in random_stream))
        fact("RANDOM costs the whole original",
             cost(random_stream) == len(corpus.RANDOM))
        fact("RANDOM decodes", s5.lz77_decode(random_stream)
             == corpus.RANDOM)

        # EMPTY through the cost model
        fact("EMPTY costs nothing",
             cost(s5.lz77_encode(corpus.EMPTY, 256, 3, 255)) == 0)

        if problems:
            raise AssertionError("%d facts failed" % (len(problems),))
        print("check_05: PASS (%d facts)" % (facts,))
        return 0
    finally:
        if root:
            sys.path[:] = [p for p in sys.path
                           if p not in (course, os.path.join(course,
                                                             "solutions"))]
        if root:
            shutil.rmtree(root, ignore_errors=True)

# --- stage 6 -----------------------------------------------------------------------
def check_6():
    import os
    import sys
    import shutil
    import subprocess
    import hashlib
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "compression-from-scratch"

    STAGE = 6

    STUB_MESSAGE = "stage 6: implement lz4_block_encode()"

    def _repo(start=None):
        for candidate_start in (os.getcwd(), os.environ.get("H7_REPO"), start,
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "corpus.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set H7_REPO=/path/to/learn-stuff-from-scratch")

    def _harness_env(root):
        """Copy the repo's course into `root` with solutions/ overlaid."""
        repo = _repo(HERE)
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course)
        overlay = os.path.join(repo, COURSE, "solutions")
        if not os.path.isdir(overlay):
            overlay = os.path.join(repo, COURSE)
        for name in os.listdir(overlay):
            source = os.path.join(overlay, name)
            if os.path.isdir(source):
                continue
            shutil.copy2(source, os.path.join(course, name))

    def _refuses(exc, what, call, names=()):
        """`call()` must raise `exc` naming every string in `names`;
        `what` is the fact's label."""
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

    def _run_py(course, snippet):
        """A snippet with the course dir importable: exit code + output."""
        code = ("import sys; sys.path.insert(0, %r)\n"
                % (course,)) + snippet
        proc = subprocess.run([sys.executable, "-c", code],
                              capture_output=True, text=True, timeout=120)
        return proc.returncode, proc.stdout + proc.stderr

    def _template_verdict():
        """The template must be the exit-2 refusal, with its own message."""
        repo = _repo(HERE)
        root = tempfile.mkdtemp(prefix="h7_check06_tpl_")
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course)
        try:
            code = ("import sys; sys.path.insert(0, %r)\n"
                    "import stage_06 as s6\n"
                    "stub = 0\n"
                    "for call in (lambda: s6.lz4_block_encode(b'abc'),\n"
                    "             lambda: s6.lz4_block_encode(b'')):\n"
                    "    try:\n"
                    "        call()\n"
                    "    except NotImplementedError as e:\n"
                    "        assert 'implement' in str(e), e\n"
                    "        stub += 1\n"
                    "    except AttributeError:\n"
                    "        stub += 1\n"
                    "if stub == 2:\n"
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
                    if os.path.isfile(os.path.join(p, "corpus.py"))
                    and os.path.isfile(os.path.join(p, "stage_01.py"))), None)
    if ambient is not None:
        root = None  # the ambient tree is the one under test; do not rmtree it
        course = ambient
    else:
        root = tempfile.mkdtemp(prefix="h7_check06_env_")
        course = os.path.join(root, COURSE)
        _harness_env(root)  # copy the repo's course in, solutions overlaid
        sys.path.insert(0, course)
    try:
        import corpus
        import lz4ref
        import stage_05 as s5
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

        # --- the world's pins, re-read (the check is not above the world)
        sizes = {"TEXT": 1874, "JSON_LIKE": 8033, "BINARY": 2608,
                 "RANDOM": 1024, "EMPTY": 0}
        for name in corpus.CORPORA:
            data = getattr(corpus, name)
            must("corpus %s is bytes" % (name,), isinstance(data, bytes))
            must("corpus %s size" % (name,), len(data) == sizes[name])
            must("corpus %s sha pinned" % (name,),
                 hashlib.sha256(data).hexdigest() == corpus.digest(name))
        must("the world's lz4 bar is pinned",
             ("TEXT", "lz4", 550) in corpus.BARS)

        # --- the template's surface exists in full; the stub's own
        # refusal is the exit-2 verdict, so probe it before anything
        stub = 0
        try:
            s6.lz4_block_encode(b"abc")
        except NotImplementedError:
            stub += 1
        except s6.EncodeError:
            pass
        try:
            s6.lz4_block_encode(corpus.EMPTY)
        except NotImplementedError:
            stub += 1
        except s6.EncodeError:
            pass
        if stub:
            print("check_06: stage 6: not implemented yet "
                  "(%d of the stage's names are still stubs)"
                  % (stub,))
            raise SystemExit(2)
        must("EncodeError exists", hasattr(s6, "EncodeError")
             and issubclass(s6.EncodeError, ValueError))

        # --- the format's shape, byte for byte: the token's nibbles,
        # the literals inline, the little-endian offset, the 255s.
        # These are also the pins the mutation battery swings at.
        must("two literals are two token bytes",
             s6.lz4_block_encode(b"ab") == b"\x20ab")
        must("a run of four is five bytes",
             s6.lz4_block_encode(b"aaaa") == b"\x40aaaa")
        must("a run of ten is a literal and a length-8 match",
             s6.lz4_block_encode(b"a" * 10)
             == b"\x14a\x01\x00\x10a")
        must("a length-20 match extends the low nibble",
             s6.lz4_block_encode(b"a" * 20)
             == b"\x1e\x61\x01\x00\x10\x61")
        must("a length-40 match ends its extension at 25",
             s6.lz4_block_encode(b"a" * 40)
             == b"\x1f\x61\x01\x00\x13\x10\x61")
        must("a length-10 match is one 255-extension",
             s6.lz4_block_encode(b"ab" * 10)
             == b"\x2d\x61\x62\x02\x00\x10\x62")
        must("a 6-byte match on 6 bytes is literals-only",
             s6.lz4_block_encode(b"abcabc") == b"\x60abcabc")
        must("an 8-byte match ends as match plus one literal",
             s6.lz4_block_encode(b"abcabcab")
             == b"\x30\x61\x62\x63\x03\x00\x10\x62")
        must("a repeat at distance 5 keeps the big end in the high byte",
             s6.lz4_block_encode(b"abcdXabcd")
             == b"\x90\x61\x62\x63\x64\x58\x61\x62\x63\x64")
        must("a 15-byte first sequence's literal length extends",
             s6.lz4_block_encode(bytes(range(15)) + bytes(range(12)))
             == (b"\xf7\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09"
                 b"\x0a\x0b\x0c\x0d\x0e\x0f\x00\x10\x0b"))
        must("a 27-byte run of distinct bytes is literals-only",
             s6.lz4_block_encode(bytes(range(48, 75)))
             == b"\xf0\x0c" + bytes(range(48, 75)))

        must("a 16-byte literal length takes its first extension byte",
             s6.lz4_block_encode(bytes(range(48, 64)))
             == b"\xf0\x01" + bytes(range(48, 64)))

        # --- the empty input: the empty block
        must("EMPTY encodes to the empty block",
             s6.lz4_block_encode(corpus.EMPTY) == b"")

        # --- the reference decoder is the judge: every corpus decodes
        for name in corpus.CORPORA:
            data = getattr(corpus, name)
            block = s6.lz4_block_encode(data)
            fact("%s round-trips through the reference" % (name,),
                 lz4ref.lz4_block_decode(block) == data)

        # --- the encoder's refusals: a caller's mistake, named
        _refuses(s6.EncodeError, "a str is refused",
                 lambda: s6.lz4_block_encode("text"), names=("str",))
        _refuses(s6.EncodeError, "an int is refused",
                 lambda: s6.lz4_block_encode(7), names=("int",))
        _refuses(s6.EncodeError, "a list is refused",
                 lambda: s6.lz4_block_encode([104, 105]), names=("list",))
        _refuses(s6.EncodeError, "None is refused",
                 lambda: s6.lz4_block_encode(None), names=("None",))

        # --- the format's own window: no offset past 65535
        fact("the window constant is pinned",
             s6.WINDOW == 65535 and s6.MIN_MATCH == 4)
        fact("stage 5's stream obeys the format's window",
             all(item[1] <= 65535 for item in
                 s5.lz77_encode(corpus.TEXT, s6.WINDOW, s6.MIN_MATCH,
                                s6.MAX_MATCH)
                 if isinstance(item, tuple)))

        # --- determinism: the same input, the same bytes
        fact("encoding is deterministic",
             s6.lz4_block_encode(corpus.TEXT)
             == s6.lz4_block_encode(corpus.TEXT))

        # --- the bars: measured, never asserted — the world's own pair
        text_block = s6.lz4_block_encode(corpus.TEXT)
        text_permille = len(text_block) * 1000 // len(corpus.TEXT)
        print("  ratio TEXT: %d per-mille (bar 550)"
              % (text_permille,))
        fact("TEXT clears the world's bar",
             text_permille <= 550)
        json_block = s6.lz4_block_encode(corpus.JSON_LIKE)
        json_permille = len(json_block) * 1000 // len(corpus.JSON_LIKE)
        print("  ratio JSON_LIKE: %d per-mille" % (json_permille,))
        binary_block = s6.lz4_block_encode(corpus.BINARY)
        binary_permille = len(binary_block) * 1000 // len(corpus.BINARY)
        print("  ratio BINARY: %d per-mille" % (binary_permille,))
        fact("JSON_LIKE compresses", json_permille < 1000)
        fact("BINARY compresses", binary_permille < 1000)

        # --- RANDOM: incompressible, the block grows by the token tax
        random_block = s6.lz4_block_encode(corpus.RANDOM)
        random_permille = len(random_block) * 1000 // len(corpus.RANDOM)
        print("  ratio RANDOM: %d per-mille" % (random_permille,))
        fact("RANDOM's block stays near its size (token tax bounded)",
             random_permille <= 1010)
        fact("RANDOM round-trips", lz4ref.lz4_block_decode(random_block)
             == corpus.RANDOM)

        if problems:
            raise AssertionError("%d facts failed" % (len(problems),))
        print("check_06: PASS (%d facts)" % (facts,))
        return 0
    finally:
        if root:
            sys.path[:] = [p for p in sys.path
                           if p not in (course, os.path.join(course,
                                                             "solutions"))]
        if root:
            shutil.rmtree(root, ignore_errors=True)

# --- stage 7 -----------------------------------------------------------------------
def check_7():
    import os
    import sys
    import shutil
    import subprocess
    import hashlib
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "compression-from-scratch"

    STAGE = 7

    STUB_MESSAGE = "stage 7: implement deflate_block()"

    def _repo(start=None):
        for candidate_start in (os.getcwd(), os.environ.get("H7_REPO"), start,
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "corpus.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set H7_REPO=/path/to/learn-stuff-from-scratch")

    def _harness_env(root):
        """Copy the repo's course into `root` with solutions/ overlaid."""
        repo = _repo(HERE)
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course)
        overlay = os.path.join(repo, COURSE, "solutions")
        if not os.path.isdir(overlay):
            overlay = os.path.join(repo, COURSE)
        for name in os.listdir(overlay):
            source = os.path.join(overlay, name)
            if os.path.isdir(source):
                continue
            shutil.copy2(source, os.path.join(course, name))

    def _refuses(exc, what, call, names=()):
        """`call()` must raise `exc` naming every string in `names`;
        `what` is the fact's label."""
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

    def _run_py(course, snippet):
        """A snippet with the course dir importable: exit code + output."""
        code = ("import sys; sys.path.insert(0, %r)\n"
                % (course,)) + snippet
        proc = subprocess.run([sys.executable, "-c", code],
                              capture_output=True, text=True, timeout=120)
        return proc.returncode, proc.stdout + proc.stderr

    def _template_verdict():
        """The template must be the exit-2 refusal, with its own message."""
        repo = _repo(HERE)
        root = tempfile.mkdtemp(prefix="h7_check07_tpl_")
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course)
        try:
            code = ("import sys; sys.path.insert(0, %r)\n"
                    "import stage_07 as s7\n"
                    "stub = 0\n"
                    "for call in (lambda: s7.deflate_block(b'abc', "
                    "'stored'),\n"
                    "             lambda: s7.deflate(b'abc')):\n"
                    "    try:\n"
                    "        call()\n"
                    "    except NotImplementedError as e:\n"
                    "        assert 'implement' in str(e), e\n"
                    "        stub += 1\n"
                    "    except AttributeError:\n"
                    "        stub += 1\n"
                    "if stub == 2:\n"
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
                    if os.path.isfile(os.path.join(p, "corpus.py"))
                    and os.path.isfile(os.path.join(p, "stage_01.py"))), None)
    if ambient is not None:
        root = None  # the ambient tree is the one under test; do not rmtree it
        course = ambient
    else:
        root = tempfile.mkdtemp(prefix="h7_check07_env_")
        course = os.path.join(root, COURSE)
        _harness_env(root)  # copy the repo's course in, solutions overlaid
        sys.path.insert(0, course)
    try:
        import corpus
        import inflate
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

        # --- the world's pins, re-read (the check is not above the world)
        sizes = {"TEXT": 1874, "JSON_LIKE": 8033, "BINARY": 2608,
                 "RANDOM": 1024, "EMPTY": 0}
        for name in corpus.CORPORA:
            data = getattr(corpus, name)
            must("corpus %s is bytes" % (name,), isinstance(data, bytes))
            must("corpus %s size" % (name,), len(data) == sizes[name])
            must("corpus %s sha pinned" % (name,),
                 hashlib.sha256(data).hexdigest() == corpus.digest(name))

        # --- the template's surface exists in full; the stub's own
        # refusal is the exit-2 verdict, so probe it before anything
        stub = 0
        try:
            s7.deflate_block(b"abc", "stored")
        except NotImplementedError:
            stub += 1
        except s7.EncodeError:
            pass
        try:
            s7.deflate(b"abc")
        except NotImplementedError:
            stub += 1
        except s7.EncodeError:
            pass
        if stub:
            print("check_07: stage 7: not implemented yet "
                  "(%d of the stage's names are still stubs)"
                  % (stub,))
            raise SystemExit(2)
        must("EncodeError exists", hasattr(s7, "EncodeError")
             and issubclass(s7.EncodeError, ValueError))

        # --- the stage's declared constants, held
        must("MODES pins the three block kinds",
             s7.MODES == ("stored", "fixed", "dynamic"))
        must("the stream's kind bits pin",
             (s7.STORED, s7.FIXED, s7.DYNAMIC) == (0, 1, 2))
        must("FINAL is the final flag", s7.FINAL == 1)
        must("the literal alphabet is 286 wide", s7.LITERALS == 286)
        must("the distance alphabet is 30 wide", s7.DISTANCES == 30)
        must("the format's width cap is fifteen", s7.MAX_WIDTH == 15)
        must("the end-of-block symbol is 256", s7.END_OF_BLOCK == 256)
        must("the window is the distance alphabet's 32 KiB",
             s7.WINDOW == 32768)
        must("a match is 3..258 bytes",
             (s7.MIN_MATCH, s7.MAX_MATCH) == (3, 258))
        must("a stored block holds 65535 bytes at most",
             s7.STORED_MAX == 0xFFFF)

        # --- every mode round-trips every corpus through the judge
        for name in corpus.CORPORA:
            data = getattr(corpus, name)
            for mode in s7.MODES:
                block = s7.deflate_block(data, mode)
                must("%s/%s: block is bytes" % (name, mode),
                     isinstance(block, bytes))
                out, bits = inflate.inflate(block)
                fact("%s: %s block decodes to the original"
                     % (name, mode), out == data)
                fact("%s: %s block consumes bits" % (name, mode),
                     bits > 0 or (not data and bits == 0))

        # --- the stored block's header: LEN and NLEN, the complement's
        # law, byte-aligned after the kind's three bits
        for name in ("TEXT", "RANDOM"):
            data = getattr(corpus, name)
            block = s7.deflate_block(data, "stored")
            length = block[1] | (block[2] << 8)
            nlen = block[3] | (block[4] << 8)
            fact("%s: stored LEN is the data's length" % (name,),
                 length == len(data))
            fact("%s: stored NLEN is LEN's complement" % (name,),
                 length ^ 0xFFFF == nlen)
            fact("%s: stored carries the bytes themselves" % (name,),
                 block[5:] == data)

        # --- the fixed block: the RFC's own code, no tree on the wire
        block = s7.deflate_block(corpus.TEXT, "fixed")
        fact("fixed block is smaller than the data",
             len(block) < len(corpus.TEXT))
        fact("fixed encoding is deterministic",
             s7.deflate_block(corpus.TEXT, "fixed") == block)

        # --- the dynamic tree: the reference reads it back, end-of-block
        # included (the reference refuses a tree without one)
        block = s7.deflate_block(corpus.TEXT, "dynamic")
        out, bits = inflate.inflate(block)
        fact("dynamic block decodes", out == corpus.TEXT)
        fact("dynamic beats fixed on TEXT", len(block) < len(
            s7.deflate_block(corpus.TEXT, "fixed")))
        # the end-of-block code is on the wire: symbol 256's width is in
        # the transmitted tree, so the decoded bit count stops at it
        fact("dynamic block's bits stop at the end-of-block",
             bits == len(block) * 8 or bits < len(block) * 8)

        # --- the per-block choice, both sides of it: RANDOM has no
        # code to build (stored wins), TEXT pays the tree back
        stored_random = s7.deflate_block(corpus.RANDOM, "stored")
        fixed_random = s7.deflate_block(corpus.RANDOM, "fixed")
        dynamic_random = s7.deflate_block(corpus.RANDOM, "dynamic")
        fact("RANDOM: stored beats fixed", len(stored_random)
             < len(fixed_random))
        fact("RANDOM: stored beats dynamic", len(stored_random)
             < len(dynamic_random))
        fact("RANDOM: deflate() chooses stored",
             s7.deflate(corpus.RANDOM) == stored_random)
        fact("RANDOM: deflate() decodes",
             inflate.inflate(s7.deflate(corpus.RANDOM))[0] == corpus.RANDOM)

        # --- the ratio bar the world pins: TEXT, deflate, 450
        stream = s7.deflate(corpus.TEXT)
        must("deflate() output is bytes", isinstance(stream, bytes))
        fact("deflate() on TEXT decodes",
             inflate.inflate(stream)[0] == corpus.TEXT)
        permille = len(stream) * 1000 // len(corpus.TEXT)
        print("  ratio TEXT: deflate = %d per-mille (bar 450)"
              % (permille,))
        fact("TEXT clears the deflate bar", permille <= 450)
        for name in ("JSON_LIKE", "BINARY"):
            data = getattr(corpus, name)
            stream = s7.deflate(data)
            fact("%s: deflate() decodes" % (name,),
                 inflate.inflate(stream)[0] == data)
            fact("%s: deflate() compresses" % (name,),
                 len(stream) < len(data))

        # --- EMPTY: the stream that is only a header
        for mode in s7.MODES:
            out, _bits = inflate.inflate(s7.deflate_block(corpus.EMPTY,
                                                          mode))
            fact("EMPTY: %s block decodes to empty" % (mode,), out == b"")
        fact("EMPTY: deflate() decodes to empty",
             inflate.inflate(s7.deflate(corpus.EMPTY))[0] == b"")

        # --- determinism: the same input, the same bytes
        for mode in s7.MODES:
            fact("%s: deterministic" % (mode,),
                 s7.deflate_block(corpus.JSON_LIKE, mode)
                 == s7.deflate_block(corpus.JSON_LIKE, mode))
        fact("deflate() deterministic",
             s7.deflate(corpus.TEXT) == s7.deflate(corpus.TEXT))

        # --- a caller's mistake raises, naming the offender
        for empty in (b"", corpus.EMPTY):
            _refuses(s7.EncodeError, "unknown mode refused",
                     lambda e=empty: s7.deflate_block(e, "huffman"),
                     names=("huffman",))
            _refuses(s7.EncodeError, "mode None refused",
                     lambda e=empty: s7.deflate_block(e, None),
                     names=("None",))
        _refuses(s7.EncodeError, "stored past LEN's width refused",
                 lambda: s7.deflate_block(bytes(0x10000), "stored"),
                 names=("65535",))

        if problems:
            raise AssertionError("%d facts failed" % (len(problems),))
        print("check_07: PASS (%d facts)" % (facts,))
        return 0
    finally:
        if root:
            sys.path[:] = [p for p in sys.path
                           if p not in (course, os.path.join(course,
                                                             "solutions"))]
        if root:
            shutil.rmtree(root, ignore_errors=True)

# --- stage 8 -----------------------------------------------------------------------
def check_8():
    import os
    import sys
    import shutil
    import subprocess
    import hashlib
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "compression-from-scratch"

    STAGE = 8

    STUB_MESSAGE = "stage 8: implement fse_build_table()"

    def _repo(start=None):
        for candidate_start in (os.getcwd(), os.environ.get("H7_REPO"), start,
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "corpus.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set H7_REPO=/path/to/learn-stuff-from-scratch")

    def _harness_env(root):
        """Copy the repo's course into `root` with solutions/ overlaid."""
        repo = _repo(HERE)
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course)
        overlay = os.path.join(repo, COURSE, "solutions")
        if not os.path.isdir(overlay):
            overlay = os.path.join(repo, COURSE)
        for name in os.listdir(overlay):
            source = os.path.join(overlay, name)
            if os.path.isdir(source):
                continue
            shutil.copy2(source, os.path.join(course, name))

    def _refuses(exc, what, call, names=()):
        """`call()` must raise `exc` naming every string in `names`;
        `what` is the fact's label."""
        try:
            call()
        except exc as raised:
            message = str(raised)
            for name in names:
                if name not in message:
                    raise AssertionError(
                        "%s: refusal does not name %r: %s" % (what, name,
                                                              message))
            return
        except Exception as raised:
            raise AssertionError("%s: wrong exception %r" % (what, raised))
        raise AssertionError("%s: no refusal" % (what,))

    def _run_py(course, snippet):
        """A snippet with the course dir importable: exit code + output."""
        code = ("import sys; sys.path.insert(0, %r)\n"
                % (course,)) + snippet
        proc = subprocess.run([sys.executable, "-c", code],
                              capture_output=True, text=True, timeout=120)
        return proc.returncode, proc.stdout + proc.stderr

    def _template_verdict():
        """The template must be the exit-2 refusal, with its own message."""
        repo = _repo(HERE)
        root = tempfile.mkdtemp(prefix="h7_check08_tpl_")
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course)
        try:
            code = ("import sys; sys.path.insert(0, %r)\n"
                    "import stage_08 as s8\n"
                    "stub = 0\n"
                    "for call in (lambda: s8.fse_build_table((1, 1), 2),\n"
                    "             lambda: s8.fse_encode(b'ab', [1, 1]),\n"
                    "             lambda: s8.fse_decode(b'\\x00' * 4,\n"
                    "                                    [1, 1], 1)):\n"
                    "    try:\n"
                    "        call()\n"
                    "    except NotImplementedError as e:\n"
                    "        assert 'implement' in str(e), e\n"
                    "        stub += 1\n"
                    "    except AttributeError:\n"
                    "        stub += 1\n"
                    "    except Exception:\n"
                    "        pass\n"
                    "if stub == 3:\n"
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
                    if os.path.isfile(os.path.join(p, "corpus.py"))
                    and os.path.isfile(os.path.join(p, "stage_01.py"))), None)
    if ambient is not None:
        root = None  # the ambient tree is the one under test; do not rmtree it
        course = ambient
    else:
        root = tempfile.mkdtemp(prefix="h7_check08_env_")
        course = os.path.join(root, COURSE)
        _harness_env(root)  # copy the repo's course in, solutions overlaid
        sys.path.insert(0, course)
    try:
        import corpus
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

        # --- the world's pins, re-read (the check is not above the world)
        sizes = {"TEXT": 1874, "JSON_LIKE": 8033, "BINARY": 2608,
                 "RANDOM": 1024, "EMPTY": 0}
        for name in corpus.CORPORA:
            data = getattr(corpus, name)
            must("corpus %s is bytes" % (name,), isinstance(data, bytes))
            must("corpus %s size" % (name,), len(data) == sizes[name])
            must("corpus %s sha pinned" % (name,),
                 hashlib.sha256(data).hexdigest() == corpus.digest(name))
        import stage_01 as s1

        # --- the template's surface exists in full; the stub's own
        # refusal is the exit-2 verdict, so probe it before anything
        stub = 0
        try:
            s8.fse_build_table((1, 1), 2)
        except NotImplementedError:
            stub += 1
        except Exception:
            pass
        try:
            s8.fse_encode(b"ab", [1, 1] + [0] * 254)
        except NotImplementedError:
            stub += 1
        except Exception:
            pass
        try:
            s8.fse_decode(b"\x00" * 4, [1, 1] + [0] * 254, 1)
        except NotImplementedError:
            stub += 1
        except Exception:
            pass
        if hasattr(s1, "EncodeError"):
            must("refusals are ValueError subclasses",
                 issubclass(s1.EncodeError, ValueError))
        if stub:
            print("check_08: stage 8: not implemented yet "
                  "(%d of the stage's names are still stubs)"
                  % (stub,))
            raise SystemExit(2)

        # --- the table's normalization: the counts sum to EXACTLY the
        # state count, and each symbol owns exactly its normalized count
        norm, spread, ranks, slots = s8.fse_build_table([5, 2, 1], 8)
        fact("normalization sums to the state count", sum(norm) == 8)
        fact("normalization pinned", norm == (5, 2, 1))
        fact("the spread covers every slot exactly once",
             sorted(spread) == [0, 0, 0, 0, 0, 1, 1, 2])
        fact("the spread is pinned",
             spread == (0, 0, 0, 0, 0, 1, 1, 2))
        fact("each symbol owns exactly its normalized count",
             [len(item) for item in slots] == [5, 2, 1])
        fact("every slot named for a symbol holds that symbol",
             all(spread[slot] == symbol
                 for symbol, owned in enumerate(slots)
                 for slot in owned))

        # --- the uniform table: the spread interleaves, the ranks are
        # dense per symbol, and the walk runs both ways off one table
        norm4, spread4, ranks4, slots4 = s8.fse_build_table(
            [4, 4, 4, 4], 16)
        fact("uniform normalization", norm4 == (4, 4, 4, 4))
        fact("uniform spread pinned",
             spread4 == (0, 1, 2, 3, 1, 2, 3, 0, 2, 3, 0, 1,
                         3, 0, 1, 2))
        fact("ranks dense per symbol, pinned for the uniform table",
             ranks4 == (0, 0, 0, 0, 1, 1, 1, 1,
                        2, 2, 2, 2, 3, 3, 3, 3))
        fact("a symbol's states see ranks 0..count-1",
             all(sorted(ranks4[slot] for slot in owned)
                 == list(range(norm4[symbol]))
                 for symbol, owned in enumerate(slots4)))

        # --- the largest-remainder law: 1,1,1,1 over 8 states gives
        # every symbol a floor of 1 and the four extra states to the
        # lowest symbols — no state invented for a symbol the data
        # never counted
        norm8 = s8.fse_build_table([1, 1, 1, 1], 8)[0]
        fact("floor of one per counted symbol",
             all(count >= 1 for count in norm8))
        fact("the extra states go to the lowest symbols",
             norm8 == (2, 2, 2, 2))

        # --- a sum > max_state is refused: the table cannot hold it
        _refuses(s1.EncodeError, "more symbols than states refused",
                 lambda: s8.fse_build_table([1] * 9, 4),
                 names=("9", "4"))

        # --- the refusals a caller's mistake owes
        _refuses(s1.EncodeError, "a negative count refused",
                 lambda: s8.fse_build_table([2, -1], 8), names=("-1",))
        _refuses(s1.EncodeError, "a non-power-of-two state count refused",
                 lambda: s8.fse_build_table([1, 1], 6), names=("6",))
        _refuses(s1.EncodeError, "a zero state count refused",
                 lambda: s8.fse_build_table([1, 1], 0), names=("0",))
        _refuses(s1.EncodeError, "a float count refused",
                 lambda: s8.fse_build_table([1.5, 1], 8), names=("1.5",))

        # --- the degenerate table: all-zero counts pre-answer symbol 0
        normz, spreadz, ranksz, slotsz = s8.fse_build_table([0, 0, 0], 4)
        fact("the degenerate table normalizes to one state",
             normz == (1, 0, 0) and sum(normz) == 1)
        fact("the degenerate spread answers symbol 0 in every state",
             spreadz == (0, 0, 0, 0) and slotsz[0] == (0, 0, 0, 0)
             and ranksz == (0, 0, 0, 0))

        # --- the round-trip: the stage's own decoder is the format,
        # so the check holds it on every corpus, counts from the data
        for name in corpus.CORPORA:
            data = getattr(corpus, name)
            counts = [0] * 256
            for byte in data:
                counts[byte] += 1
            packed, norm = s8.fse_encode(data, counts)
            fact("%s: encodes to bytes" % (name,), isinstance(packed,
                                                              bytes))
            fact("%s: the returned counts are the table's" % (name,),
                 norm == s8.fse_build_table(
                     counts, 1 << max((sum(counts) - 1).bit_length(), 0)
                 )[0] if sum(counts) else norm == (1,) + (0,) * 255)
            fact("%s: round-trips" % (name,),
                 s8.fse_decode(packed, counts, len(data)) == data)
            print("  ratio %s: %d -> %d (%d per-mille)"
                  % (name, len(data), len(packed),
                     len(packed) * 1000 // len(data) if data else 0))

        # --- the table's sum law on every corpus: whatever the walk
        # transmits, it normalizes to exactly the state count
        for name in corpus.CORPORA:
            data = getattr(corpus, name)
            counts = [0] * 256
            for byte in data:
                counts[byte] += 1
            packed, norm = s8.fse_encode(data, counts)
            state_count = 1
            if sum(counts):
                state_count = 1 << (sum(counts) - 1).bit_length()
            fact("%s: the transmitted counts sum to the state count"
                 % (name,), sum(norm) == state_count)
            table = s8.fse_build_table(counts, state_count)
            fact("%s: the decode builds the same table" % (name,),
                 table[0] == norm
                 and s8.fse_decode(packed, counts, len(data))
                 == data)

        # --- the header's tax is bounded: RANDOM's counts are flat, so
        # the table costs the stream little; the ratio proves it
        random_counts = [0] * 256
        for byte in corpus.RANDOM:
            random_counts[byte] += 1
        packed, norm = s8.fse_encode(corpus.RANDOM, random_counts)
        fact("RANDOM costs near its own size",
             len(packed) * 1000 // len(corpus.RANDOM) < 1100)

        # --- the stream's position invariance: encoding a suffix with
        # the WHOLE corpus's counts still round-trips the suffix
        text_counts = [0] * 256
        for byte in corpus.TEXT:
            text_counts[byte] += 1
        suffix = corpus.TEXT[-40:]
        packed = s8.fse_encode(suffix, text_counts)[0]
        fact("a suffix round-trips under the corpus's own counts",
             s8.fse_decode(packed, text_counts, len(suffix)) == suffix)

        # --- determinism: the same input, the same bytes
        fact("encoding is deterministic",
             s8.fse_encode(corpus.TEXT, text_counts)
             == s8.fse_encode(corpus.TEXT, text_counts))
        fact("the table is deterministic",
             s8.fse_build_table([5, 2, 1], 8)
             == s8.fse_build_table([5, 2, 1], 8))

        # --- the encoder's refusals: a caller's mistake, named
        _refuses(s1.EncodeError, "non-bytes data refused",
                 lambda: s8.fse_encode("nope", text_counts),
                 names=("nope",))
        zero_counts = [1, 0, 0]
        _refuses(s1.EncodeError, "a symbol with count 0 refused",
                 lambda: s8.fse_encode(b"\x01", zero_counts),
                 names=("1",))

        # --- the decoder's refusals: what the format forbids, named
        _refuses(s1.EncodeError, "non-bytes stream refused",
                 lambda: s8.fse_decode(42, text_counts, 3),
                 names=("42",))
        _refuses(s1.EncodeError, "a negative size refused",
                 lambda: s8.fse_decode(b"\x00" * 8, text_counts, -1),
                 names=("-1",))
        _refuses(s1.EncodeError, "a stream too short for the state",
                 lambda: s8.fse_decode(b"ab", text_counts, 3),
                 names=("2",))
        _refuses(s1.EncodeError, "a stream that ends early refused",
                 lambda: s8.fse_decode(b"\x00" * 4, text_counts, 100),
                 names=("ends",))

        if problems:
            raise AssertionError("%d facts failed" % (len(problems),))
        print("check_08: PASS (%d facts)" % (facts,))
        return 0
    finally:
        if root:
            sys.path[:] = [p for p in sys.path
                           if p not in (course, os.path.join(course,
                                                             "solutions"))]
        if root:
            shutil.rmtree(root, ignore_errors=True)

# --- stage 9 -----------------------------------------------------------------------
def check_9():
    import os
    import sys
    import shutil
    import subprocess
    import hashlib
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "compression-from-scratch"

    STAGE = 9

    STUB_MESSAGE = "stage 9: implement frame_encode()"

    def _repo(start=None):
        for candidate_start in (os.getcwd(), os.environ.get("H7_REPO"), start,
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "corpus.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set H7_REPO=/path/to/learn-stuff-from-scratch")

    def _harness_env(root):
        """Copy the repo's course into `root` with solutions/ overlaid."""
        repo = _repo(HERE)
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course)
        overlay = os.path.join(repo, COURSE, "solutions")
        if not os.path.isdir(overlay):
            overlay = os.path.join(repo, COURSE)
        for name in os.listdir(overlay):
            source = os.path.join(overlay, name)
            if os.path.isdir(source):
                continue
            shutil.copy2(source, os.path.join(course, name))

    def _refuses(exc, what, call, names=()):
        """`call()` must raise `exc` naming every string in `names`;
        `what` is the fact's label."""
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

    def _run_py(course, snippet):
        """A snippet with the course dir importable: exit code + output."""
        code = ("import sys; sys.path.insert(0, %r)\n"
                % (course,)) + snippet
        proc = subprocess.run([sys.executable, "-c", code],
                              capture_output=True, text=True, timeout=120)
        return proc.returncode, proc.stdout + proc.stderr

    def _template_verdict():
        """The template must be the exit-2 refusal, with its own message."""
        repo = _repo(HERE)
        root = tempfile.mkdtemp(prefix="h7_check09_tpl_")
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course)
        try:
            code = ("import sys; sys.path.insert(0, %r)\n"
                    "import stage_09 as s9\n"
                    "stub = 0\n"
                    "for call in (lambda: s9.frame_encode(b'abc', 'raw'),\n"
                    "             lambda: s9.frame_decode(b'abc')):\n"
                    "    try:\n"
                    "        call()\n"
                    "    except NotImplementedError as e:\n"
                    "        assert 'implement' in str(e), e\n"
                    "        stub += 1\n"
                    "    except AttributeError:\n"
                    "        stub += 1\n"
                    "if stub == 2:\n"
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
                    if os.path.isfile(os.path.join(p, "corpus.py"))
                    and os.path.isfile(os.path.join(p, "stage_01.py"))), None)
    if ambient is not None:
        root = None  # the ambient tree is the one under test; do not rmtree it
        course = ambient
    else:
        root = tempfile.mkdtemp(prefix="h7_check09_env_")
        course = os.path.join(root, COURSE)
        _harness_env(root)  # copy the repo's course in, solutions overlaid
        sys.path.insert(0, course)
    try:
        import corpus
        import inflate
        import zstdref
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

        # --- the world's pins, re-read (the check is not above the world)
        sizes = {"TEXT": 1874, "JSON_LIKE": 8033, "BINARY": 2608,
                 "RANDOM": 1024, "EMPTY": 0}
        for name in corpus.CORPORA:
            data = getattr(corpus, name)
            must("corpus %s is bytes" % (name,), isinstance(data, bytes))
            must("corpus %s size" % (name,), len(data) == sizes[name])
            must("corpus %s sha pinned" % (name,),
                 hashlib.sha256(data).hexdigest() == corpus.digest(name))

        # --- the template's surface exists in full; the stub's own
        # refusal is the exit-2 verdict, so probe it before anything
        stub = 0
        try:
            s9.frame_encode(b"abc", "raw")
        except NotImplementedError:
            stub += 1
        except ValueError:
            pass
        try:
            s9.frame_decode(b"abc")
        except NotImplementedError:
            stub += 1
        except ValueError:
            pass
        if stub:
            print("check_09: stage 9: not implemented yet "
                  "(%d of the stage's names are still stubs)"
                  % (stub,))
            raise SystemExit(2)
        must("EncodeError exists", hasattr(s9, "EncodeError")
             and issubclass(s9.EncodeError, ValueError))

        # --- the stage's declared constants, held: the frame's own
        # arithmetic is the reference frame's, borrowed not spelled
        must("the magic is the frame's", s9.MAGIC == zstdref.MAGIC)
        must("the block kinds are the frame's",
             (s9.BLOCK_RAW, s9.BLOCK_RLE, s9.BLOCK_COMPRESSED)
             == (zstdref.BLOCK_RAW, zstdref.BLOCK_RLE,
                 zstdref.BLOCK_COMPRESSED))
        must("the block size is the frame's",
             s9.BLOCK_SIZE == zstdref.BLOCK_SIZE == 4096)
        must("the modes are the frame's three",
             s9.MODES == ("raw", "rle", "compressed"))

        # --- the format's arithmetic, read off the wire: the magic,
        # the 3-byte little-endian content size, the block-size byte,
        # the flags, then each block's kind, its 3-byte size, its bytes
        for name in ("TEXT", "JSON_LIKE"):
            data = getattr(corpus, name)
            frame = s9.frame_encode(data, "raw")
            must("%s: the frame starts with the magic" % (name,),
                 frame[:4] == zstdref.MAGIC)
            must("%s: the content size is little-endian" % (name,),
                 frame[4:7] == len(data).to_bytes(3, "little"))
            must("%s: the block-size byte names 4096" % (name,),
                 frame[7] == 12)
            must("%s: the flags byte is 0" % (name,), frame[8] == 0)
            must("%s: the checksum rides the content's hash" % (name,),
                 frame[-4:] == zstdref.checksum(data).to_bytes(4, "little"))
            # walk the blocks: every chunk is one block, raw mode's
            # content is the bytes themselves
            at = 9
            blocks = []
            while at < len(frame) - 4:
                kind = frame[at]
                size = int.from_bytes(frame[at + 1:at + 4], "little")
                blocks.append((kind, size, frame[at + 4:at + 4 + size]))
                at += 4 + size
            chunks = [data[start:start + s9.BLOCK_SIZE]
                      for start in range(0, len(data), s9.BLOCK_SIZE)]
            fact("%s: raw mode's blocks are the content verbatim" % (name,),
                 len(blocks) == len(chunks)
                 and all(kind == s9.BLOCK_RAW and content == chunk
                         for (kind, _size, content), chunk
                         in zip(blocks, chunks)))

        # --- every mode round-trips every corpus, through the stage's
        # own reader AND the reference's where the reference carries
        # the blocks (raw and RLE: the judge; compressed blocks are the
        # stage's own reader's to decode — the reference names the
        # handoff itself)
        for name in corpus.CORPORA:
            data = getattr(corpus, name)
            for mode in s9.MODES:
                frame = s9.frame_encode(data, mode)
                must("%s/%s: the frame is bytes" % (name, mode),
                     isinstance(frame, bytes))
                fact("%s: %s frame round-trips" % (name, mode),
                     s9.frame_decode(frame) == data)
                try:
                    verdict = zstdref.frame_decode(frame)
                except zstdref.FrameError as problem:
                    # only the compressed-block handoff is allowed to
                    # refuse; the refusal must NAME the handoff
                    verdict = None
                    fact("%s: %s frame's refusal is the handoff"
                         % (name, mode),
                         mode == "compressed" and "compressed" in str(problem))
                else:
                    fact("%s: %s frame is the reference's cargo too"
                         % (name, mode), verdict == data)

        # --- the raw frame agrees with the world's own recipe,
        # byte for byte (verify_provided's own construction)
        data = corpus.TEXT[:5000]
        expected = bytearray(zstdref.MAGIC + len(data).to_bytes(3, "little")
                             + bytes([12]) + bytes([0]))
        for at in range(0, len(data), zstdref.BLOCK_SIZE):
            block = data[at:at + zstdref.BLOCK_SIZE]
            expected += (bytes([zstdref.BLOCK_RAW])
                         + len(block).to_bytes(3, "little") + block)
        expected += zstdref.checksum(data).to_bytes(4, "little")
        fact("raw mode's frame is the world's own recipe, byte for byte",
             s9.frame_encode(data, "raw") == bytes(expected))

        # --- the RLE pin, both sides: the kind is spent only on a
        # whole BLOCK_SIZE run of one byte (one byte on the wire, the
        # reader's BLOCK_SIZE expansion filling the header's count);
        # anything else rides raw — and the reference agrees with both
        run = bytes([0x5A]) * s9.BLOCK_SIZE
        frame = s9.frame_encode(run, "rle")
        fact("a whole block's run is an RLE block", frame[9] == s9.BLOCK_RLE)
        fact("the RLE block carries exactly one byte",
             int.from_bytes(frame[10:13], "little") == 1
             and frame[13] == 0x5A)
        fact("the RLE frame round-trips", s9.frame_decode(frame) == run)
        fact("the RLE frame is the reference's cargo too",
             zstdref.frame_decode(frame) == run)
        short = bytes([0x5A]) * (s9.BLOCK_SIZE - 1)
        frame = s9.frame_encode(short, "rle")
        fact("a shorter run rides raw", frame[9] == s9.BLOCK_RAW)
        fact("the shorter run's frame round-trips",
             s9.frame_decode(frame) == short)
        fact("the shorter run's frame is the reference's cargo too",
             zstdref.frame_decode(frame) == short)
        # rle mode on BINARY: the runs pay the kind where the pin lets
        # them, the frame still answers the corpus
        frame = s9.frame_encode(corpus.BINARY, "rle")
        fact("BINARY's rle frame round-trips",
             s9.frame_decode(frame) == corpus.BINARY)
        fact("BINARY's rle frame is the reference's cargo too",
             zstdref.frame_decode(frame) == corpus.BINARY)

        # --- the compressed block: the payload is exactly what
        # `s7.deflate_block` answers and the stage's own reader decodes
        # it with the reference inflate — one mode per block, the
        # stream's final flag inside the payload, the inflate's bit
        # count reaching the content's last byte
        import stage_07 as s7

        def _walk(frame):
            """The frame's blocks as (kind, size, content) triples."""
            at = 9
            blocks = []
            while at < len(frame) - 4:
                kind = frame[at]
                size = int.from_bytes(frame[at + 1:at + 4], "little")
                blocks.append((kind, size,
                               frame[at + 4:at + 4 + size]))
                at += 4 + size
            return blocks

        frame = s9.frame_encode(corpus.TEXT, "compressed")
        blocks = _walk(frame)
        fact("TEXT: the compressed mode spends the compressed kind",
             any(kind == s9.BLOCK_COMPRESSED
                 for kind, _s, _c in blocks))
        # every compressed block's payload is one complete deflate
        # stream: the reference inflate decodes it, the decoded bytes
        # are the chunk the header's offset names, and the bits reach
        # into the content's last byte (the rest is padding)
        at = 0
        for kind, _size, content in blocks:
            if kind != s9.BLOCK_COMPRESSED:
                at += len(content)
                continue
            out, bits = inflate.inflate(content)
            fact("TEXT: a compressed block inflates to its chunk",
                 out == corpus.TEXT[at:at + len(out)])
            at += len(out)
            fact("TEXT: the compressed block's bits reach the "
                 "content's last byte", bits > (len(content) - 1) * 8)
        fact("TEXT: the compressed blocks rebuild the content",
             at == len(corpus.TEXT))
        # the payload is deflate_block's answer, byte for byte: re-derive
        # the encoder's choice and compare
        chunk = corpus.TEXT[:s9.BLOCK_SIZE]
        payloads = sorted((len(s7.deflate_block(chunk, m)), m,
                           s7.deflate_block(chunk, m)) for m in s7.MODES)
        best = payloads[0][2]
        if len(best) < len(chunk):
            frame = s9.frame_encode(chunk, "compressed")
            fact("the compressed payload is deflate_block's answer",
                 frame[13:13 + len(best)] == best)
        fact("the compressed frame round-trips",
             s9.frame_decode(s9.frame_encode(corpus.TEXT, "compressed"))
             == corpus.TEXT)

        # --- the compressed mode's raw escape: a full block of noise
        # has no mode under BLOCK_SIZE (stored alone is five over), so
        # the chunk rides raw — pinned by measurement, not hope. The
        # noise is the world's own LCG recipe: deterministic, and no
        # code builds for it.
        state = 987
        noise = bytearray()
        for _ in range(5120):          # one full block, a tail
            state = (state * 6364136223846793005 + 1442695040888963407) \
                & ((1 << 64) - 1)
            noise.append((state >> 33) & 0xFF)
        noise = bytes(noise)
        frame = s9.frame_encode(noise, "compressed")
        noise_kinds = [kind for kind, _s, _c in _walk(frame)]
        fact("a full block of noise rides raw under compressed mode",
             noise_kinds[0] == s9.BLOCK_RAW)
        fact("the noise frame round-trips", s9.frame_decode(frame) == noise)
        fact("the noise frame is the reference's cargo too",
             zstdref.frame_decode(frame) == noise)

        # --- the bar the world pins: TEXT, frame, 450
        frame = s9.frame_encode(corpus.TEXT, "compressed")
        permille = len(frame) * 1000 // len(corpus.TEXT)
        print("  ratio TEXT: frame = %d per-mille (bar 450)" % (permille,))
        fact("TEXT clears the frame bar", permille <= 450)

        # --- EMPTY: a frame whose content size is 0 and no blocks,
        # both readers accepting it
        for mode in s9.MODES:
            frame = s9.frame_encode(corpus.EMPTY, mode)
            fact("EMPTY: %s frame is header and checksum only" % (mode,),
                 len(frame) == 13)
            fact("EMPTY: %s frame's size field is 0" % (mode,),
                 frame[4:7] == b"\x00\x00\x00")
            fact("EMPTY: %s frame round-trips" % (mode,),
                 s9.frame_decode(frame) == b"")
            fact("EMPTY: %s frame is the reference's cargo too" % (mode,),
                 zstdref.frame_decode(frame) == b"")

        # --- determinism: the same input, the same bytes
        for mode in s9.MODES:
            fact("%s: deterministic" % (mode,),
                 s9.frame_encode(corpus.JSON_LIKE, mode)
                 == s9.frame_encode(corpus.JSON_LIKE, mode))

        # --- a caller's mistake raises, naming the offender
        _refuses(s9.EncodeError, "unknown mode refused",
                 lambda: s9.frame_encode(b"abc", "huffman"),
                 names=("huffman",))
        _refuses(s9.EncodeError, "mode None refused",
                 lambda: s9.frame_encode(b"abc", None), names=("None",))
        _refuses(s9.EncodeError, "non-bytes data refused",
                 lambda: s9.frame_encode("text", "raw"), names=("bytes",))

        # --- the reader's refusals: every one the format forbids,
        # each named
        good = s9.frame_encode(corpus.TEXT, "raw")

        def torn(off, count=1):
            bad = bytearray(good)
            for i in range(count):
                bad[off + i] ^= 0xFF
            return bytes(bad)

        _refuses(s9.EncodeError, "a frame too short refused",
                 lambda: s9.frame_decode(good[:11]), names=("12",))
        _refuses(s9.EncodeError, "a bad magic refused",
                 lambda: s9.frame_decode(b"XXXX" + good[4:]), names=("magic",))
        _refuses(s9.EncodeError, "bad flags refused",
                 lambda: s9.frame_decode(good[:8] + bytes([1]) + good[9:]),
                 names=("flags",))
        _refuses(s9.EncodeError, "a bad block-size byte refused",
                 lambda: s9.frame_decode(good[:7] + bytes([13]) + good[8:]),
                 names=("block",))
        _refuses(s9.EncodeError, "an undefined block kind refused",
                 lambda: s9.frame_decode(good[:9] + bytes([3]) + good[10:]),
                 names=("kind",))
        # a block whose content overruns the frame: the first block's
        # size is grown past what the frame holds
        overrun = bytearray(good)
        overrun[10:13] = (4096).to_bytes(3, "little")
        _refuses(s9.EncodeError, "a content overrun refused",
                 lambda: s9.frame_decode(bytes(overrun)),
                 names=("overruns",))
        # a content size that disagrees with the header
        _refuses(s9.EncodeError, "a lying content size refused",
                 lambda: s9.frame_decode(good[:4]
                                         + (len(corpus.TEXT) + 1).to_bytes(
                                             3, "little") + good[7:]),
                 names=("header",))
        # the compressed reader's own law: a stream that stops short
        # of the block's content is a torn block. Hand-built, because
        # the encoder never writes one: a valid frame whose compressed
        # block's content is stretched by one byte, its checksum
        # recomputed so the SIZE law does not answer first — only the
        # reach law can refuse this frame.
        stretch = bytearray(s9.frame_encode(corpus.TEXT, "compressed"))
        at = 9
        while at < len(stretch) - 4:
            kind = stretch[at]
            size = int.from_bytes(stretch[at + 1:at + 4], "little")
            if kind == s9.BLOCK_COMPRESSED:
                content_at = at + 4
                stretch[content_at:content_at + size] = \
                    bytes(stretch[content_at:content_at + size]) + b"\x00"
                stretch[at + 1:at + 4] = (size + 1).to_bytes(3, "little")
                stretch[4:7] = (len(corpus.TEXT)).to_bytes(3, "little")
                body = bytes(stretch[9:len(stretch)])
                # the checksum must now cover the OLD content: the
                # stretched byte is not cargo, so the content's hash
                # is unchanged — recompute and rewrite it
                stretch[len(stretch) - 4:] = \
                    zstdref.checksum(corpus.TEXT).to_bytes(4, "little")
                _ = body
                break
            at += 4 + size
        _refuses(s9.EncodeError,
                 "a compressed stream short of its content is refused",
                 lambda: s9.frame_decode(bytes(stretch)),
                 names=("content",))

        # --- the checksum's law: one flipped bit in the CONTENT —
        # first byte, a middle byte, the last byte — or in the
        # CHECKSUM's own bytes is noticed, each refusal naming the
        # checksum. (A header byte's flip is the header's own law,
        # held above.)
        flips = [9 + 4,                             # the first content byte
                 9 + 4 + s9.BLOCK_SIZE // 2,        # a middle content byte
                 9 + 4 + len(corpus.TEXT) - 1,      # the last content byte
                 len(good) - 4,                     # the checksum's first byte
                 len(good) - 1]                     # the checksum's own byte
        for off in flips:
            if off < len(good):
                _refuses(s9.EncodeError,
                         "a flipped bit at %d is noticed" % (off,),
                         lambda o=off: s9.frame_decode(torn(o)),
                         names=("checksum",))

        # the same flips, held against the reference: its law and the
        # stage's agree on the frames it reads
        for off in (9 + 4, len(good) - 1):
            _refuses(zstdref.FrameError,
                     "the reference notices the flip at %d too" % (off,),
                     lambda o=off: zstdref.frame_decode(torn(o)))

        # --- the multi-block tail: a corpus past one block exercises
        # the block walk's boundaries on all three modes
        wide = corpus.TEXT + corpus.JSON_LIKE  # 9907 bytes, three blocks
        for mode in s9.MODES:
            frame = s9.frame_encode(wide, mode)
            fact("the wide corpus's %s frame round-trips" % (mode,),
                 s9.frame_decode(frame) == wide)
            try:
                verdict = zstdref.frame_decode(frame)
            except zstdref.FrameError:
                fact("the wide corpus's %s handoff is named" % (mode,),
                     mode == "compressed")
            else:
                fact("the wide corpus's %s frame agrees" % (mode,),
                     verdict == wide)

        if problems:
            raise AssertionError("%d facts failed" % (len(problems),))
        print("check_09: PASS (%d facts)" % (facts,))
        return 0
    finally:
        if root:
            sys.path[:] = [p for p in sys.path
                           if p not in (course, os.path.join(course,
                                                             "solutions"))]
        if root:
            shutil.rmtree(root, ignore_errors=True)

# --- stage 10 ----------------------------------------------------------------------
def check_10():
    import os
    import sys
    import shutil
    import subprocess
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "compression-from-scratch"

    STAGE = 10

    STUB_MESSAGE = "stage 10: implement prove()"

    def _repo(start=None):
        for candidate_start in (os.getcwd(), os.environ.get("H7_REPO"), start,
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "corpus.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set H7_REPO=/path/to/learn-stuff-from-scratch")

    def _harness_env(root):
        """Copy the repo's course into `root` with solutions/ overlaid."""
        repo = _repo(HERE)
        course = os.path.join(root, COURSE)
        shutil.copytree(os.path.join(repo, COURSE), course)
        overlay = os.path.join(repo, COURSE, "solutions")
        if not os.path.isdir(overlay):
            overlay = os.path.join(repo, COURSE)
        for name in os.listdir(overlay):
            source = os.path.join(overlay, name)
            if os.path.isdir(source):
                continue
            shutil.copy2(source, os.path.join(course, name))

    def _refuses(exc, what, call, names=()):
        """`call()` must raise `exc` naming every string in `names`;
        `what` is the fact's label."""
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

    def _run_py(course, snippet):
        """A snippet with the course dir importable: exit code + output."""
        code = ("import sys; sys.path.insert(0, %r)\n"
                % (course,)) + snippet
        proc = subprocess.run([sys.executable, "-c", code],
                              capture_output=True, text=True, timeout=120)
        return proc.returncode, proc.stdout + proc.stderr

    def _template_verdict():
        """The template must be the exit-2 refusal, with its own message.
        The copied course's solutions/ stays OFF the path: only the
        template's stage_10 is importable here."""
        repo = _repo(HERE)
        root = tempfile.mkdtemp(prefix="h7_check10_tpl_")
        course = os.path.join(root, COURSE)
        try:
            shutil.copytree(os.path.join(repo, COURSE), course)
            code = ("import sys; sys.path.insert(0, %r)\n"
                    "import stage_10 as s10\n"
                    "stub = 0\n"
                    "for call in (lambda: s10.prove('TEXT'),\n"
                    "             lambda: s10.audit({})):\n"
                    "    try:\n"
                    "        call()\n"
                    "    except NotImplementedError as e:\n"
                    "        assert 'implement' in str(e), e\n"
                    "        stub += 1\n"
                    "if stub == 2:\n"
                    "    print('not implemented yet')\n"
                    "    raise SystemExit(42)\n"
                    "raise SystemExit(7)\n" % (course,))
            proc = subprocess.run([sys.executable, "-c", code],
                                  capture_output=True, text=True, timeout=120)
            if proc.returncode == 42 and "not implemented yet" in proc.stdout:
                return 0
            print("template: expected the stub refusal, got %d: %s"
                  % (proc.returncode, (proc.stdout + proc.stderr)[:400]))
            return 1
        finally:
            shutil.rmtree(root, ignore_errors=True)

    ambient = next((p for p in sys.path
                    if os.path.isfile(os.path.join(p, "corpus.py"))
                    and os.path.isfile(os.path.join(p, "stage_01.py"))), None)
    if ambient is not None:
        root = None  # the ambient tree is the one under test; do not rmtree it
        course = ambient
    else:
        root = tempfile.mkdtemp(prefix="h7_check10_env_")
        course = os.path.join(root, COURSE)
        _harness_env(root)  # copy the repo's course in, solutions overlaid
        sys.path.insert(0, course)
    try:
        import corpus
        import zstdref
        import stage_01 as s1
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

        # --- the world's pins, re-read: the bars are the audit's law
        must("the bars are the world's",
             corpus.BARS == (("BINARY", "rle", 700), ("TEXT", "huffman", 650),
                             ("TEXT", "lz4", 550), ("TEXT", "deflate", 450),
                             ("TEXT", "frame", 450)))
        must("the corpora are five",
             corpus.CORPORA == ("TEXT", "JSON_LIKE", "BINARY", "RANDOM",
                                "EMPTY"))

        # --- the template's surface: the stage's own constants, held
        must("PROOF_KEYS is the template's",
             s10.PROOF_KEYS == ("ratios", "verdicts", "round_trips"))
        must("AUDIT_KEYS is the template's",
             s10.AUDIT_KEYS == ("verdict", "reasons"))

        # --- the stub's own refusal is the exit-2 verdict, so probe it
        stub = 0
        try:
            s10.prove("TEXT")
        except NotImplementedError:
            stub += 1
        try:
            s10.audit({})
        except NotImplementedError:
            stub += 1
        if stub:
            print("check_10: stage 10: not implemented yet "
                  "(%d of the stage's names are still stubs)"
                  % (stub,))
            raise SystemExit(2)

        # --- prove over every corpus: the keys are the template's, the
        # records are per-codec, and the flipped bit is noticed
        proofs = {}
        for name in corpus.CORPORA:
            proof = s10.prove(name)
            fact("%s: the proof's keys are the template's" % (name,),
                 tuple(proof.keys()) == s10.PROOF_KEYS)
            fact("%s: the proof carries every codec" % (name,),
                 set(proof["ratios"]) == {"rle", "huffman", "lz4", "deflate",
                                          "fse", "frame"}
                 and set(proof["verdicts"]) >= {"rle", "huffman", "lz4",
                                                "deflate", "fse", "frame",
                                                "flipped_bit"}
                 and set(proof["round_trips"]) == {"rle", "huffman", "lz4",
                                                   "deflate", "fse", "frame"})
            fact("%s: the ratios are ints" % (name,),
                 all(isinstance(value, int) and not isinstance(value, bool)
                     for value in proof["ratios"].values()))
            fact("%s: the round-trips are booleans" % (name,),
                 all(value is True or value is False
                     for value in proof["round_trips"].values()))
            fact("%s: the flipped bit is noticed" % (name,),
                 proof["verdicts"]["flipped_bit"] == "noticed")
            # the reference verdicts are acceptance, the self-judged
            # codecs ride their round-trips, and the round-trips are exact
            for codec in ("lz4", "deflate", "frame"):
                fact("%s/%s: the reference accepts" % (name, codec),
                     proof["verdicts"][codec] == "accepted")
            for codec in ("rle", "huffman", "fse"):
                fact("%s/%s: the round-trip is the verdict" % (name, codec),
                     proof["verdicts"][codec] == "round_trip")
            fact("%s: every round-trip is exact" % (name,),
                 all(proof["round_trips"].values()))
            proofs[name] = proof

        # --- the ratios are measured, not asserted: re-measure one
        # codec's bytes against the proof's own number
        import stage_03 as s3
        encoded, _lengths = s3.huffman_encode(corpus.TEXT)
        fact("TEXT/huffman: the ratio is the measured bytes",
             proofs["TEXT"]["ratios"]["huffman"]
             == len(encoded) * 1000 // len(corpus.TEXT))

        # --- the world's bars: every bar cleared by the proof's ratio
        for bar_corpus, codec, bar in corpus.BARS:
            ratio = proofs[bar_corpus]["ratios"][codec]
            fact("%s/%s: ratio %d clears the bar %d"
                 % (bar_corpus, codec, ratio, bar), ratio <= bar)

        # --- the verdicts are not prose: the reference is genuinely
        # asked, so a frame the reference refuses cannot say accepted
        import stage_09 as s9
        raw = s9.frame_encode(corpus.TEXT, "raw")
        fact("the raw frame is the reference's cargo",
             zstdref.frame_decode(raw) == corpus.TEXT)

        # --- audit: the whole course grades `pass`
        audit = s10.audit(proofs)
        must("the audit's keys are the template's",
             tuple(audit.keys()) == s10.AUDIT_KEYS)
        fact("the audit's verdict is pass", audit["verdict"] == "pass")
        fact("a pass names no reasons", audit["reasons"] == ())

        # --- audit on tampered proofs: each cut is named with its
        # (corpus, codec) pair, and the grade is fail
        def _tampered(mutate):
            broken = {name: {key: dict(value) if isinstance(value, dict)
                             else value
                             for key, value in proof.items()}
                      for name, proof in proofs.items()}
            mutate(broken)
            return s10.audit(broken)

        grade = _tampered(lambda p: p["TEXT"]["ratios"].__setitem__(
            "lz4", 999))
        fact("a ratio over the bar fails",
             grade["verdict"] == "fail"
             and any("TEXT/lz4" in reason for reason in grade["reasons"]))
        grade = _tampered(lambda p: p["TEXT"]["verdicts"].__setitem__(
            "lz4", "refused"))
        fact("a refused reference fails",
             grade["verdict"] == "fail"
             and any("TEXT/lz4" in reason for reason in grade["reasons"]))
        grade = _tampered(lambda p: p["TEXT"]["round_trips"].__setitem__(
            "fse", False))
        fact("a broken round-trip fails",
             grade["verdict"] == "fail"
             and any("TEXT/fse" in reason for reason in grade["reasons"]))
        grade = _tampered(lambda p: p["TEXT"]["verdicts"].__setitem__(
            "huffman", "broken"))
        fact("a broken self-judged verdict fails",
             grade["verdict"] == "fail"
             and any("TEXT/huffman" in reason for reason in grade["reasons"]))
        grade = _tampered(lambda p: p["BINARY"]["verdicts"].__setitem__(
            "flipped_bit", "unnoticed"))
        fact("an unnoticed flip fails",
             grade["verdict"] == "fail"
             and any("BINARY/flipped_bit" in reason
                     for reason in grade["reasons"]))

        # --- the refusals: `prove` names a corpus the world does not
        # have, and a caller's mistake raises as the course's law asks
        _refuses(s1.EncodeError, "prove refuses an unknown corpus",
                 lambda: s10.prove("NOSUCH"),
                 names=("NOSUCH", "corpus"))

        # --- the flipped bit is the proof's own case, re-enacted: one
        # bit in the content, and BOTH readers refuse
        import stage_02 as s2
        frame = s9.frame_encode(corpus.BINARY, "raw")
        flipped = frame[:13] + bytes([frame[13] ^ 1]) + frame[14:]
        for reader, label in ((s9.frame_decode, "the stage's reader"),
                              (zstdref.frame_decode, "the reference")):
            _refuses(ValueError, "%s refuses the flipped frame" % (label,),
                     lambda reader=reader: reader(flipped))
        fact("the flip did change the frame", flipped != frame)
        fact("the unflipped frame still reads",
             s9.frame_decode(frame) == corpus.BINARY
             and zstdref.frame_decode(frame) == corpus.BINARY)

        # --- the flipped bit's other end: the proof's own verdict
        # holds for a corpus whose first block IS the cargo (BINARY
        # above) and for the empty corpus's checksum-only frame
        empty_frame = s9.frame_encode(corpus.EMPTY, "raw")
        empty_flipped = empty_frame[:-1] + bytes([empty_frame[-1] ^ 1])
        _refuses(ValueError, "the empty frame's flipped checksum is noticed",
                 lambda: zstdref.frame_decode(empty_flipped))

        # --- laws: no floats anywhere in the stage, no banned imports
        import ast
        with open(os.path.join(course, "solutions", "stage_10.py")) as fh:
            tree = ast.parse(fh.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value,
                                                             float):
                fact("no float literal in the stage", False)
            if isinstance(node, ast.Import):
                fact("the stage imports only world and stages",
                     all(alias.name in ("corpus", "inflate", "lz4ref",
                                        "zstdref", "stage_01", "stage_02",
                                        "stage_03", "stage_06", "stage_07",
                                        "stage_08", "stage_09")
                         for alias in node.names))

        # --- the stage is importable with nothing else on the path
        code, out = _run_py(course, "import stage_10\n")
        fact("the stage imports in a bare course dir", code == 0)

        if problems:
            raise AssertionError("%d facts failed" % (len(problems),))
        print("check_10: PASS (%d facts)" % (facts,))
        return 0
    finally:
        sys.path[:] = [p for p in sys.path
                       if p not in (course, os.path.join(course,
                                                         "solutions"))]
        if root:
            shutil.rmtree(root, ignore_errors=True)

# --- the manifest. One entry per stage, in the order a reader meets them.

STAGES = [
    stage(
        1,
        file="stage_01.py",
        title='The bit writer: LSB-first, widths that fit',
        tags=['bits', 'LSB-first', 'writer'],
        action="Write `BitWriter`, `write_bits` and `bit_length_of` in stage_01.py.",
        predict="Why the bit order is the format's own and what a writer that masks corrupts without saying so.",
        check=check_1,
    ),
    stage(
        2,
        file="stage_02.py",
        title='Run-length: the format that cannot fail',
        tags=['rle', 'marker', 'ratio'],
        action="Write `rle_encode` and `rle_decode` in stage_02.py.",
        predict="Why the marker's economy is measurable on runs and bounded on noise, and why an unescaped marker corrupts silently.",
        check=check_2,
    ),
    stage(
        3,
        file="stage_03.py",
        title='Canonical Huffman: codes from lengths',
        tags=['huffman', 'canonical', 'kraft'],
        action="Write `huffman_lengths`, `canonical_codes`, `huffman_encode` and `huffman_decode` in stage_03.py.",
        predict='Why the lengths are the code and how the canonical order makes two encoders byte-identical.',
        check=check_3,
    ),
    stage(
        4,
        file="stage_04.py",
        title='The length limit: a code that fits the writer',
        tags=['limit', 'package-merge', 'widths'],
        action="Write `limit_lengths` in stage_04.py.",
        predict="Why Kraft's sum must come back to exactly one and what the limit costs the frequent symbols.",
        check=check_4,
    ),
    stage(
        5,
        file="stage_05.py",
        title='LZ77: the window and the matches',
        tags=['lz77', 'window', 'matches'],
        action="Write `lz77_encode` and `lz77_decode` in stage_05.py.",
        predict='Why the window is the whole trade and why the overlap is copied byte by byte.',
        check=check_5,
    ),
    stage(
        6,
        file="stage_06.py",
        title="LZ4's block format: nibbles and extensions",
        tags=['lz4', 'block-format', 'nibbles'],
        action="Write `lz4_block_encode` in stage_06.py.",
        predict="Why the token's nibbles are the format's economy and why the reference decoder is the judge.",
        check=check_6,
    ),
    stage(
        7,
        file="stage_07.py",
        title='DEFLATE: stored, static, dynamic',
        tags=['deflate', 'stored', 'dynamic'],
        action="Write `deflate_block` and `deflate` in stage_07.py.",
        predict="Why the mode is chosen per block and what LEN's complement protects.",
        check=check_7,
    ),
    stage(
        8,
        file="stage_08.py",
        title='FSE: the table the format builds',
        tags=['fse', 'ans', 'table'],
        action="Write `fse_build_table`, `fse_encode` and `fse_decode` in stage_08.py.",
        predict='Why the table is the format and why the decoder is stage code.',
        check=check_8,
    ),
    stage(
        9,
        file="stage_09.py",
        title='The frame: a header, blocks, and a checksum',
        tags=['frame', 'checksum', 'container'],
        action="Write `frame_encode` and `frame_decode` in stage_09.py.",
        predict='Why the checksum rides the content and what the flipped bit proves.',
        check=check_9,
    ),
    stage(
        10,
        file="stage_10.py",
        title='The proof: every codec, every corpus, one verdict',
        tags=['proof', 'bars', 'audit'],
        action="Write `PROOF_KEYS`, `prove`, `AUDIT_KEYS` and `audit` in stage_10.py.",
        predict="Why the bars are the grade and why the audit reads the reference decoders' verdicts.",
        check=check_10,
    ),
]
