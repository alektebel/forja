"""Agentic Retrieval From Scratch — course manifest.

Ten graded stages between a corpus of contracts and an answer that can defend
itself. The world is provided and complete and frozen: `corpus.py` is the
customer's library — the documents as their lawyers wrote them (numbered
clauses, cross-references, defined terms, a duplicated number, a skipped one and
a document that supersedes another), an analyzer, an inverse document frequency
in basis points, an embedder whose vectors are unit-scaled so that a similarity
is a plain dot product, a glossary of the customer's own acronyms, and the three
records the course is held against: the clause index (what a clause *is*), the
labelled questions (what the right answer cites) and the failure log (which stage
of the old pipeline failed, with the evidence behind it); `meter.py` is what a
decision costs — a price table in cents and a ledger the meter recounts from its
own charges.

The thesis of the whole course is one sentence, and every stage's check asserts
it: RETRIEVAL THAT CHECKS ITSELF IS A PIPELINE OF SMALL, NAMED VERDICTS — A CHUNK
THAT CAN BE CITED, A RANK THAT CAN BE JUSTIFIED, A QUESTION THAT WAS MADE
UNAMBIGUOUS, A CRITIQUE THAT NAMES THE OFFENDER, AN ABSTENTION THAT SAYS WHY, AND
A COST HELD AGAINST THE NAIVE BASELINE RATHER THAN ASSERTED. Each stage exists
because the one before it left a hole: a chunk that splits a clause, or loses the
cross-reference that gives it meaning, can never be cited, and a citation to the
wrong span is the first lie in the pipeline; ten million documents are a number
before they are a system, so what is indexed, what a query touches and what it
costs are decisions, and a plan that cannot pay is refused rather than promised;
which scorer to use is answered by the customer's own labelled questions and not
by an opinion about embeddings; a reranker that cannot beat the noise it was
added against is removed; half of "the RAG is wrong" is the question, so the
pronoun, the acronym and the two-hop reference are resolved *and written down*; a
chunk that is stale, off-topic, in conflict or unresolvable is named — with its
offender — before anything answers from it; an answer is claims each tied to a
span or an abstention with a reason, and there is no third shape; searching again
is the skill, so the loop must terminate, must not retry a query it already tried
and must price every round; the naive retrieve-and-answer is the null hypothesis,
so checking yourself has to pay for itself; and the customer's failures are
labelled with the stage that failed, so the debugger has to agree with the person
who debugged it.

The failures worth preventing are the ones that look like success: a chunker that
splits a clause at a sentence and a citation that points at the half it kept; a
plan whose memory is rounded down, so the index that fits in the spreadsheet does
not fit in the machine; a fusion that sums `1 // rank` and orders every hit by
nothing; a reranker kept because it was added, not because it paid; a pronoun
resolved against the question instead of the conversation, and an acronym dropped
instead of expanded; a stale clause that answers anyway because nobody asked the
document whether it had been superseded; a claim synthesized from the model's own
words where the chunk's text belonged; a loop that checks its budget after the
call, retries the query it just tried, or never stops at all; an ROI report that
compares two pipelines with one number and calls the difference progress; and a
debugger that agrees with itself while disagreeing with the person who filed the
ticket.

Standard library only, offline, deterministic, **ints only** (every count, price,
length, rank and basis point — there is no float literal anywhere in this
course): no `time`, no `threading`, no `asyncio`, no `random`, no `os`, no
`uuid`, no `socket`, no `subprocess`, no `secrets`, no `shutil`, no `tempfile`,
no `pathlib`, and no `math`, `statistics`, `decimal` or `fractions` either —
there is no square root and no logarithm in the course, because the world hands
back a unit-scaled vector and an inverse document frequency, so a similarity is a
dot product and a rank weight is a division. The clock is the caller's, a budget
is a cent count the caller supplied, and the world is never written by the
course: a stage calls `Corpus` and `Meter`, remembers what it needs in a
structure it owns, and the world's log is how the check proves what it did.

This is the retrieval that argues with itself, and the two courses it leans on
are the retrieval half of the catalogue and its measurement: `rag-from-scratch`
(phase B1) chunks and retrieves, `vector-index-from-scratch` (B2) is the index
underneath, `evals-from-scratch` (C1) and `eval-framework-from-scratch` (F2) are
the harness that grades an answer, and `agents-from-scratch` (C2) is the loop
that decides to search again. Here the corpus is a customer's, the labels are the
customer's own, and the pipeline has to say out loud what it did, what it cost and
what it could not answer.

    python3 codecraft/cli.py run agentic-retrieval-from-scratch
"""

from codecraft.api import stage

TITLE = "Agentic Retrieval From Scratch"
DESCRIPTION = ("Retrieval that checks itself, as data: a contract chunker held "
               "against the customer's own clause index, an index plan for ten "
               "million documents that is refused when it cannot pay, BM25 and "
               "dense scoring fused by reciprocal rank and measured on labelled "
               "questions, a reranker that is removed unless it beats the noise, "
               "an ambiguous question rewritten and recorded, a critique that "
               "names a stale, conflicting, unresolvable or off-topic chunk, "
               "answers that are claims with citations or an abstention with a "
               "reason, a budgeted loop that cannot repeat itself, the cost of "
               "checking held against the naive baseline, and a debugger that has "
               "to agree with the customer's own diagnosis of which stage failed.")

LEVEL = "advanced"
ORDER = 30


# --- stage 1 -----------------------------------------------------------------------
def check_1():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "agentic-retrieval-from-scratch"

    S1_CHUNK_KEYS = ("doc", "clause", "level", "text", "refs", "defines")

    S1_PARSE_PROBLEMS = ("no-clauses", "duplicate-clause", "skipped-number", "empty-clause")

    S1_LEVELS = (1, 2, 3)

    S1_DOCUMENTS = 8

    S1_CLAUSES = 107

    def _repo(start=None):
        for candidate_start in (os.environ.get("K1_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "course.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set K1_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked
        against the message: an exception of the right family raised for the wrong
        reason is not the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return refused
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    S1_BLANK = {"doc": "syn-0", "title": "Blank", "version": 1, "superseded_by": None,
                "text": "prose with no numbered clause at all.\n"}

    S1_SYNTH = {
        "doc": "syn-1", "title": "Synthetic", "version": 1, "superseded_by": None,
        "text": ("1. Scope\n"
                 "1.1 see 4.1 and 4.1 again, under 9.9.\n"
                 "1.2 \"Zeta\" means the limit described in 1.1, and \"Alpha\" shall "
                 "mean its twin.\n"
                 "1.2(b) the sub-cap, pursuant to 2.1.\n"
                 "1.3 the \"Schedule\" is attached, and see 9.9 and then 4.1.\n"
                 "2. Term\n"
                 "2.1 \"Zeta\" means a second, later definition.\n")}

    S1_WRAPPED = {
        "doc": "syn-4", "title": "Wrapped", "version": 1, "superseded_by": None,
        "text": ("1. Scope\n"
                 "1.1 the body of the first clause runs onto\n"
                 "a second line that is not a clause at all.\n"
                 "2. Term\n"
                 "2.1 the term began in\n"
                 "2024 and continues for three years.\n")}

    S1_EMPTY = {"doc": "syn-2", "title": "Empty", "version": 1, "superseded_by": None,
                "text": "1. Heading\n1.1 \n2. Body\n"}

    S1_EMPTY_CHUNK = {"doc": "syn-3", "clause": "3.1", "level": 2, "text": "  ",
                      "refs": (), "defines": ()}

    def _s1_by_clause(chunks):
        """A chunk list by its clause id — the id two clauses may share."""
        found = {}
        for chunk in chunks:
            found.setdefault(chunk["clause"], chunk)
        return found

    def _s1_spread(record, s):
        """Every chunk of every document, in document order, as one tuple."""
        every = []
        for document in record.documents:
            every.extend(s.chunk(document)[0])
        return tuple(every)

    def _s1_constants(s):
        """The three public constants, in order: a mutation that moves one is caught."""
        assert tuple(s.CHUNK_KEYS) == S1_CHUNK_KEYS, (
            "CHUNK_KEYS is %r, and a chunk is the six keys %r" % (s.CHUNK_KEYS, S1_CHUNK_KEYS))
        assert tuple(s.PARSE_PROBLEMS) == S1_PARSE_PROBLEMS, (
            "PARSE_PROBLEMS is %r, and the closed vocabulary is %r"
            % (s.PARSE_PROBLEMS, S1_PARSE_PROBLEMS))
        assert tuple(s.LEVELS) == S1_LEVELS, (
            "LEVELS is %r, and a numbering token sits at %r" % (s.LEVELS, S1_LEVELS))

    def _s1_clauses(s, world):
        """The chunker reproduces the customer's record for every document, key for key."""
        record = world.Corpus.build(7)
        documents = record.documents
        assert len(documents) == S1_DOCUMENTS, (
            "the corpus holds %d documents, not %d" % (len(documents), S1_DOCUMENTS))
        for document in documents:
            chunks, problems = s.chunk(document)
            ids = tuple(chunk["clause"] for chunk in chunks)
            assert ids == tuple(record.clause_index(document["doc"])), (
                "the clauses of %s are not the customer's clause index, and they were %r"
                % (document["doc"], ids))
            for chunk in chunks:
                assert tuple(chunk) == S1_CHUNK_KEYS, (
                    "a chunk's keys are %r, and a chunk is %r" % (tuple(chunk), S1_CHUNK_KEYS))
                assert chunk["doc"] == document["doc"], (
                    "a chunk of %s names the document %r" % (document["doc"], chunk["doc"]))
                assert chunk["level"] in S1_LEVELS, (
                    "the level of %s is %r, and a level is one of %r"
                    % (chunk["clause"], chunk["level"], S1_LEVELS))
                assert chunk["text"].strip() != "", (
                    "the text of %s is empty, and every clause of this corpus has one"
                    % (chunk["clause"],))
                assert s.chunk_id(chunk) == "%s:%s" % (document["doc"], chunk["clause"]), (
                    "the id of %s is %r" % (chunk["clause"], s.chunk_id(chunk)))
            assert s.problems_of(chunks) == problems, (
                "the problems of %s read from the chunks are %r, and `chunk` said %r"
                % (document["doc"], s.problems_of(chunks), problems))
        msa = _s1_by_clause(s.chunk(record.document("msa-3"))[0])
        assert msa["1."]["level"] == 1 and msa["1."]["text"] == "Interpretation", (
            "a level-1 clause keeps its dot and its own text, and it was %r"
            % (msa["1."],))
        assert msa["1.1"]["level"] == 2 and msa["4.2(a)"]["level"] == 3, (
            "level 2 is `N.M` and level 3 is `N.M.L(a)`, and they were %r and %r"
            % (msa["1.1"]["level"], msa["4.2(a)"]["level"]))

    def _s1_refs(s, world):
        """The references a clause's own text carries, normalized and deduplicated."""
        record = world.Corpus.build(7)
        msa = _s1_by_clause(s.chunk(record.document("msa-3"))[0])
        assert msa["2.3"]["refs"] == ("2.2", "7.2"), (
            "the references of 2.3 are %r, and they are the numbers its own text carries, "
            "in first-appearance order" % (msa["2.3"]["refs"],))
        assert msa["3.3"]["refs"] == ("4.2(a)",), (
            "the references of 3.3 are %r, and `4.2(a)` is one reference"
            % (msa["3.3"]["refs"],))
        assert msa["1."]["refs"] == (), (
            "a clause heading with no reference has no refs, and it had %r"
            % (msa["1."]["refs"],))
        assert msa["3.2"]["refs"] == (), (
            "`within 30 days` is a count, not a reference, and 3.2's refs were %r"
            % (msa["3.2"]["refs"],))
        support = _s1_by_clause(s.chunk(record.document("sup-1"))[0])
        assert support["2.1"]["refs"] == (), (
            "`a Severity 1 incident` is not a reference, and 2.1's refs were %r"
            % (support["2.1"]["refs"],))
        synthetic, problems = s.chunk(S1_SYNTH)
        by = _s1_by_clause(synthetic)
        assert by["1.1"]["refs"] == ("4.1", "9.9"), (
            "the references of syn-1:1.1 are %r, and the same number twice is one reference"
            % (by["1.1"]["refs"],))
        assert by["1.2(b)"]["refs"] == ("2.1",), (
            "a reference with a letter is one reference, and it was %r"
            % (by["1.2(b)"]["refs"],))
        assert by["1.3"]["refs"] == ("9.9", "4.1"), (
            "the references of syn-1:1.3 are %r, and they stand in the order the text "
            "carries them, not in order of value" % (by["1.3"]["refs"],))
        assert problems == (), (
            "a synthetic document with no duplicate and no skip has no problem, and it had "
            "%r" % (problems,))

    def _s1_definitions(s, world):
        """Term -> the first definition's chunk id, and a redefinition shadows nothing."""
        record = world.Corpus.build(7)
        every = _s1_spread(record, s)
        found = s.definitions(every)
        assert found.get("Force Majeure") == "msa-3:6.1", (
            "`Force Majeure` is defined in msa-3:6.1, and the map said %r"
            % (found.get("Force Majeure"),))
        assert found.get("Services") == "msa-3:1.1", (
            "`Services` is defined in msa-3:1.1, and the map said %r"
            % (found.get("Services"),))
        assert found.get("Licence") == "amd-3:2.1", (
            "`Licence` is defined in amd-3:2.1, and the map said %r"
            % (found.get("Licence"),))
        assert found.get("Service Credits") == "sup-1:4.1", (
            "`Service Credits` is defined in sup-1:4.1, and the map said %r"
            % (found.get("Service Credits"),))
        synthetic, _ = s.chunk(S1_SYNTH)
        redefined = s.definitions(synthetic)
        assert redefined.get("Zeta") == "syn-1:1.2", (
            "`Zeta` is first defined in syn-1:1.2, and a later redefinition shadows "
            "nothing, but the map said %r" % (redefined.get("Zeta"),))
        assert "Schedule" not in redefined, (
            "a quoted term the clause does not define is not a definition, and the map "
            "holds %r" % (redefined.get("Schedule"),))
        by = _s1_by_clause(synthetic)
        assert by["1.2"]["defines"] == ("Zeta", "Alpha"), (
            "the terms of syn-1:1.2 are %r, in first-appearance order"
            % (by["1.2"]["defines"],))
        assert by["1.3"]["defines"] == (), (
            "syn-1:1.3 defines nothing, and it defined %r" % (by["1.3"]["defines"],))
        assert s.definitions(()) == {}, (
            "no chunks define nothing, and it answered %r" % (s.definitions(()),))

    def _s1_wrapped(s):
        """A clause runs to the next one, and a count is not a clause number."""
        chunks, problems = s.chunk(S1_WRAPPED)
        ids = tuple(chunk["clause"] for chunk in chunks)
        assert ids == ("1.", "1.1", "2.", "2.1"), (
            "a line that does not open a clause is a continuation of the one before it, and "
            "the clauses were %r" % (ids,))
        by = _s1_by_clause(chunks)
        assert by["1.1"]["text"] == ("the body of the first clause runs onto a second line "
                                     "that is not a clause at all."), (
            "a clause's text is its own lines joined with single spaces, and it was %r"
            % (by["1.1"]["text"],))
        assert by["2.1"]["text"] == "the term began in 2024 and continues for three years.", (
            "`2024` opens no clause because a numbering token carries a full stop, and the "
            "text was %r" % (by["2.1"]["text"],))
        assert problems == (), (
            "the wrapped document has no duplicate, no skip and no empty text, and it "
            "showed %r" % (problems,))

    def _s1_resolve(s, world):
        """`resolve` answers the chunk a bare ref names within its own document, or `None`."""
        record = world.Corpus.build(7)
        chunks, _ = s.chunk(record.document("dpa-1"))
        assert s.resolve(chunks, "9.9") is None, (
            "9.9 is a reference dpa-1 does not hold, so it resolves to nothing")
        found = s.resolve(chunks, "5.1")
        assert found is not None and found["clause"] == "5.1", (
            "5.1 is a clause of dpa-1, and resolve answered %r" % (found,))
        assert s.chunk_id(found) == "dpa-1:5.1", (
            "resolve answers the chunk itself, and its id was %r" % (s.chunk_id(found),))
        assert s.resolve(chunks, "4.2(a)") is None, (
            "a ref that only another document holds resolves to nothing here, and it "
            "answered %r" % (s.resolve(chunks, "4.2(a)"),))
        synthetic, _ = s.chunk(S1_SYNTH)
        assert s.resolve(synthetic, "4.1") is None, (
            "syn-1 does not hold 4.1, so it resolves to nothing")
        agreement = s.chunk(record.document("msa-3"))[0]
        both = [chunk for chunk in agreement if chunk["clause"] == "5.2"]
        assert len(both) == 2, (
            "the agreement holds a clause numbered 5.2 twice, and it held %d" % (len(both),))
        assert s.resolve(agreement, "5.2") == both[0], (
            "resolve answers the first chunk with that clause, and it answered %r"
            % (s.resolve(agreement, "5.2"),))

    def _s1_refs_of(s, world):
        """The closure follows refs, excludes the chunk, and survives a cycle."""
        record = world.Corpus.build(7)
        chunks, _ = s.chunk(record.document("msa-3"))
        assert s.refs_of(chunks, "msa-3:2.3") == ("msa-3:2.2", "msa-3:7.2", "msa-3:2.1"), (
            "the closure of 2.3 is its own refs first and then theirs, in discovery order, "
            "and it was %r" % (s.refs_of(chunks, "msa-3:2.3"),))
        closure = s.refs_of(chunks, "msa-3:3.3")
        assert closure == ("msa-3:4.2(a)",), (
            "3.3 refers to 4.2(a), which refers back to 3.3: the cycle guard leaves one "
            "chunk and stops, and the closure was %r" % (closure,))
        for chunk in chunks:
            cid = s.chunk_id(chunk)
            assert cid not in s.refs_of(chunks, cid), (
                "refs_of of %s holds %s itself" % (cid, cid))
        _refuses(ValueError, "refs_of of an id the list does not hold",
                 lambda: s.refs_of(chunks, "msa-3:9.9"), names=("msa-3:9.9",))

    def _s1_outline(s, world):
        """The outline is the (chunk id, level) pairs, in document order."""
        record = world.Corpus.build(7)
        chunks, _ = s.chunk(record.document("sup-1"))
        assert s.outline(chunks) == tuple((s.chunk_id(c), c["level"]) for c in chunks), (
            "the outline is the (chunk id, level) pairs, and it was %r" % (s.outline(chunks),))
        assert s.outline(chunks)[0] == ("sup-1:1.", 1), (
            "the support schedule opens at clause `1.` at level 1, and the outline began %r"
            % (s.outline(chunks)[0],))
        assert [pair for pair in s.outline(chunks) if pair[0] == "sup-1:3.3"] == \
            [("sup-1:3.3", 2)], (
                "3.3 sat at level 2, and the outline said %r"
                % ([pair for pair in s.outline(chunks) if pair[0] == "sup-1:3.3"],))

    def _s1_problems(s, world):
        """The two odd things the agreement shows, and the two no document shows."""
        record = world.Corpus.build(7)
        msa = s.chunk(record.document("msa-3"))[1]
        assert msa == (("duplicate-clause", "5.2"), ("skipped-number", "5.2")), (
            "msa-3 uses 5.2 twice and then skips it, so its problems are one duplicate and "
            "one skip, in PARSE_PROBLEMS order, and they were %r" % (msa,))
        sup = s.chunk(record.document("sup-1"))[1]
        assert sup == (("skipped-number", "3.3"),), (
            "sup-1 numbers 3.1 and then 3.3, so it skips once, and it reported %r" % (sup,))
        for document in record.documents:
            problems = s.chunk(document)[1]
            ranks = [S1_PARSE_PROBLEMS.index(name) for name, _ in problems]
            assert ranks == sorted(ranks), (
                "the problems of %s are not in PARSE_PROBLEMS order: %r"
                % (document["doc"], problems))
            for name, offender in problems:
                assert name in S1_PARSE_PROBLEMS, (
                    "a problem is one of %r, and %r is not" % (S1_PARSE_PROBLEMS, name))
                assert offender is not None and offender != "", (
                    "a problem names its offender, and %r named %r" % (name, offender))
        assert s.problems_of((S1_EMPTY_CHUNK,)) == (("empty-clause", "syn-3:3.1"),), (
            "a chunk with an empty text is an `empty-clause` problem, and it read %r"
            % (s.problems_of((S1_EMPTY_CHUNK,)),))
        assert s.chunk(S1_EMPTY)[1] == (("empty-clause", "syn-2:1.1"),), (
            "a clause whose body is empty is an `empty-clause` problem, and it read %r"
            % (s.chunk(S1_EMPTY)[1],))
        assert s.chunk(S1_BLANK) == ((), (("no-clauses", "syn-0"),)), (
            "a document with no numbered clause answers no chunks and one `no-clauses` "
            "problem, and it answered %r" % (s.chunk(S1_BLANK),))
        assert s.problems_of(()) == (), (
            "an empty chunk list has no document to name, so it shows no problem, and it "
            "showed %r" % (s.problems_of(()),))

    def _s1_refusals(s):
        """Every shape that cannot be the thing raises, and names what arrived."""
        _refuses(ValueError, "chunk of a mapping that is not a document",
                 lambda: s.chunk({"doc": 1}), names=("doc", "text"))
        _refuses(ValueError, "chunk of a string that is not a document",
                 lambda: s.chunk("msa-3"), names=("doc", "text"))
        _refuses(ValueError, "chunk of a record whose text is not a string",
                 lambda: s.chunk({"doc": "syn-9", "title": "t", "version": 1,
                                  "superseded_by": None, "text": 5}),
                 names=("doc", "text"))
        _refuses(ValueError, "chunk_id of a chunk with no doc",
                 lambda: s.chunk_id({"clause": "1."}), names=("doc", "clause"))
        _refuses(ValueError, "chunk_id of something that is not a chunk",
                 lambda: s.chunk_id("msa-3:1."), names=("doc", "clause"))

    def _s1_ledger(s, world):
        """The world recounts itself, and the chunker never asked it to analyze anything."""
        record = world.Corpus.build(7)
        before = record.stats()
        for document in record.documents:
            record.clause_index(document["doc"])
        after = record.stats()
        assert after["documents"] == S1_DOCUMENTS and after["clauses"] == S1_CLAUSES, (
            "the customer's record holds %d documents and %d clauses, and stats says %r"
            % (S1_DOCUMENTS, S1_CLAUSES, after))
        assert after["lookups"] == before["lookups"] + S1_DOCUMENTS, (
            "the record was asked for %d clause indexes, and the log says %r"
            % (S1_DOCUMENTS, after))
        assert after["analyses"] == 0 and after["idfs"] == 0 and after["embeds"] == 0, (
            "the chunker analyzed or embedded the customer's text, and the library's log "
            "says %r" % (after,))
        fresh = world.Corpus.build(7)
        _refuses(ValueError, "chunk of a malformed document",
                 lambda: s.chunk({"doc": 1}), names=("doc", "text"))
        assert fresh.stats()["lookups"] == 0 and fresh.stats()["analyses"] == 0, (
            "a refused chunk wrote to the customer's library, and it holds %r"
            % (fresh.stats(),))

    def _s1_workload(s, world):
        """One whole pass of the stage over the corpus and its synthetic documents."""
        record = world.Corpus.build(7)
        answers = []
        for document in record.documents:
            chunks, problems = s.chunk(document)
            answers.append((tuple(chunks), tuple(problems)))
            answers.append(tuple(s.chunk_id(chunk) for chunk in chunks))
            answers.append(s.outline(chunks))
            answers.append(tuple(sorted(s.definitions(chunks).items())))
        agreement = s.chunk(record.document("msa-3"))[0]
        answers.append(s.refs_of(agreement, "msa-3:2.3"))
        answers.append(s.refs_of(agreement, "msa-3:3.3"))
        answers.append(s.chunk(record.document("dpa-1")))
        answers.append(s.chunk(S1_SYNTH))
        answers.append(s.chunk(S1_WRAPPED))
        answers.append(s.chunk(S1_BLANK))
        answers.append(s.chunk(S1_EMPTY))
        return tuple(answers)

    def _s1_twice(s, world):
        one = _s1_workload(s, world)
        two = _s1_workload(s, world)
        assert one == two, (
            "two runs of one workload answered differently, so a run is not a function of "
            "its inputs")

    import stage_01 as s
    import corpus as world
    _s1_constants(s)
    _s1_clauses(s, world)
    _s1_refs(s, world)
    _s1_definitions(s, world)
    _s1_wrapped(s)
    _s1_resolve(s, world)
    _s1_refs_of(s, world)
    _s1_outline(s, world)
    _s1_problems(s, world)
    _s1_refusals(s)
    _s1_ledger(s, world)
    _s1_twice(s, world)

# --- stage 2 -----------------------------------------------------------------------
def check_2():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "agentic-retrieval-from-scratch"

    S2_LAYOUTS = ("flat", "sharded-by-doc", "two-tier")

    S2_PROBLEMS = ("over-budget", "scan-too-wide")

    S2_PLAN_KEYS = ("layout", "shards", "postings", "memory_mb", "scan_bp", "index_cents",
                    "query_cents", "verdict", "problems")

    S2_CLAIMS = ("layout", "shards", "postings", "memory_mb", "scan_bp", "clauses-scanned",
                 "index_cents", "query_cents")

    S2_WEIGH_KEYS = ("clauses", "terms", "postings", "posting_bytes", "dictionary_bytes",
                     "vector_bytes", "bytes", "memory_mb", "hot_clauses")

    S2_SCALE = {"documents": 10000000, "clauses": 140000000, "terms": 250000,
                "bytes_per_clause": 480, "hot_bp": 2000}

    S2_SCALE_KEYS = ("documents", "clauses", "terms", "bytes_per_clause", "hot_bp")

    S2_COUNTERS = ("analyses", "idfs", "embeds", "lookups")

    def _repo(start=None):
        for candidate_start in (os.environ.get("K1_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                here = os.path.join(candidate, COURSE)
                if (os.path.isfile(os.path.join(here, "course.py"))
                        or os.path.isfile(os.path.join(here, "corpus.py"))):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set K1_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked
        against the message: an exception of the right family raised for the wrong
        reason is not the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return refused
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _s2_mb(byte_count):
        """Whole megabytes, rounded up, in the check's own arithmetic."""
        return (byte_count + 1048576 - 1) // 1048576

    def _s2_bills(scale, dim):
        """The estate's three bills, its postings and its hot clauses, recomputed here."""
        postings = scale["clauses"] * 4
        posting_bytes = postings * 8
        dictionary_bytes = scale["terms"] * 64
        vector_bytes = scale["clauses"] * dim * 2
        hot = scale["clauses"] * scale["hot_bp"] // 10000
        return postings, posting_bytes, dictionary_bytes, vector_bytes, hot

    def _s2_hot_scale():
        """The estate with every clause hot, so a two-tier plan keeps every vector."""
        return dict(S2_SCALE, hot_bp=10000)

    def _s2_workload(stage, world):
        """One whole pass of the stage over the world's own estate, as one tuple."""
        scale = world.SCALE
        hot = _s2_hot_scale()
        generous = _s2_mb(6288000000) + 100
        return (stage.weigh(scale),
                stage.weigh(hot),
                stage.bytes_of("flat", 1, scale),
                stage.bytes_of("sharded-by-doc", 64, scale),
                stage.bytes_of("two-tier", 64, scale),
                stage.scan_of("flat", 64, scale),
                stage.scan_of("sharded-by-doc", 8, scale),
                stage.scan_of("two-tier", 4, scale),
                stage.plan(scale, generous),
                stage.plan(scale, 1),
                stage.plan(hot, 1),
                stage.explain(stage.plan(scale, generous)))

    def _s2_constants(s, world):
        assert tuple(s.LAYOUTS) == S2_LAYOUTS, (
            "LAYOUTS is %r, and the plan's tie-break is the order %r"
            % (tuple(s.LAYOUTS), S2_LAYOUTS))
        assert tuple(s.PLAN_PROBLEMS) == S2_PROBLEMS, (
            "PLAN_PROBLEMS is %r, not the closed vocabulary %r"
            % (tuple(s.PLAN_PROBLEMS), S2_PROBLEMS))
        assert tuple(s.PLAN_KEYS) == S2_PLAN_KEYS, (
            "PLAN_KEYS is %r, not %r" % (tuple(s.PLAN_KEYS), S2_PLAN_KEYS))
        for name, want in (("POSTING_BYTES", 8), ("TERM_BYTES", 64), ("VECTOR_BYTES", 2),
                           ("BYTES_PER_MB", 1048576), ("POSTINGS_PER_CLAUSE", 4),
                           ("SCAN_BUDGET_BP", 2500), ("MAX_SHARDS", 64),
                           ("INDEX_CENTS_PER_MILLION_POSTINGS", 40),
                           ("QUERY_CENTS_PER_MILLION_SCANNED", 60)):
            got = getattr(s, name)
            assert got == want, ("%s is %r, and the customer's own table says %r"
                                 % (name, got, want))
        assert issubclass(s.PlanError, ValueError), (
            "PlanError stands outside ValueError, so a caller's `except ValueError` no "
            "longer catches a broken plan: %r" % (s.PlanError.__mro__,))
        assert tuple(world.SCALE_KEYS) == S2_SCALE_KEYS, (
            "the world's estate has the keys %r, not %r" % (tuple(world.SCALE_KEYS),
                                                            S2_SCALE_KEYS))
        assert world.SCALE == S2_SCALE, (
            "the world's estate is %r, not the frozen %r" % (world.SCALE, S2_SCALE))
        assert world.VECTOR_DIM == 32, (
            "the world's vector dimension is %r, not 32" % (world.VECTOR_DIM,))

    def _s2_weigh(s, world):
        scale = world.SCALE
        weighed = s.weigh(scale)
        assert tuple(weighed) == S2_WEIGH_KEYS, (
            "weigh's keys are %r, not %r" % (tuple(weighed), S2_WEIGH_KEYS))
        postings, posting_bytes, dictionary_bytes, vector_bytes, hot = _s2_bills(
            scale, world.VECTOR_DIM)
        total = posting_bytes + dictionary_bytes + vector_bytes
        assert weighed["clauses"] == scale["clauses"], (
            "weigh's clauses are %r, not the estate's %r"
            % (weighed["clauses"], scale["clauses"]))
        assert weighed["terms"] == scale["terms"], (
            "weigh's terms are %r, not the estate's %r" % (weighed["terms"], scale["terms"]))
        assert weighed["postings"] == postings, (
            "the postings are %r, not the clauses' own %r" % (weighed["postings"], postings))
        assert weighed["posting_bytes"] == posting_bytes, (
            "the posting bytes are %r, not %r" % (weighed["posting_bytes"], posting_bytes))
        assert weighed["dictionary_bytes"] == dictionary_bytes, (
            "the dictionary bytes are %r, not %r"
            % (weighed["dictionary_bytes"], dictionary_bytes))
        assert weighed["vector_bytes"] == vector_bytes, (
            "the vector bytes are %r, not %r" % (weighed["vector_bytes"], vector_bytes))
        assert weighed["bytes"] == total, (
            "the estate's bytes are %r, not the three bills' own %r"
            % (weighed["bytes"], total))
        assert weighed["memory_mb"] == _s2_mb(total), (
            "the memory is %r, and rounding the %d bytes up gives %r"
            % (weighed["memory_mb"], total, _s2_mb(total)))
        assert weighed["memory_mb"] == 12833, (
            "the estate's memory is %r, and the contract says 12833"
            % (weighed["memory_mb"],))
        assert weighed["memory_mb"] != total // 1048576, (
            "the memory was rounded down: %r is the floor of %d bytes, not the ceiling"
            % (weighed["memory_mb"], total))
        assert weighed["hot_clauses"] == hot, (
            "the hot clauses are %r, not the estate's own %r" % (weighed["hot_clauses"], hot))
        assert weighed["hot_clauses"] == 28000000, (
            "the hot clauses are %r, and 2%% of 140M is 28000000" % (weighed["hot_clauses"],))

    def _s2_bytes_of(s, world):
        scale = world.SCALE
        postings, posting_bytes, dictionary_bytes, vector_bytes, hot = _s2_bills(
            scale, world.VECTOR_DIM)
        flat = posting_bytes + dictionary_bytes + vector_bytes
        two_tier = posting_bytes + dictionary_bytes + hot * world.VECTOR_DIM * 2
        assert s.bytes_of("flat", 1, scale) == flat, (
            "a flat index holds %r bytes, not the estate's own %d"
            % (s.bytes_of("flat", 1, scale), flat))
        assert s.bytes_of("flat", 64, scale) == flat, (
            "a flat layout's bytes move with the shard count: %r"
            % (s.bytes_of("flat", 64, scale),))
        assert s.bytes_of("sharded-by-doc", 1, scale) == flat, (
            "one shard holds %r bytes, not the flat estate's %d"
            % (s.bytes_of("sharded-by-doc", 1, scale), flat))
        assert s.bytes_of("sharded-by-doc", 4, scale) == posting_bytes + 4 * dictionary_bytes + vector_bytes, (
            "four shards pay %r bytes, and four dictionaries are %d more than one"
            % (s.bytes_of("sharded-by-doc", 4, scale), 3 * dictionary_bytes))
        assert s.bytes_of("sharded-by-doc", 64, scale) == posting_bytes + 64 * dictionary_bytes + vector_bytes, (
            "sixty-four shards pay %r bytes, not a dictionary per shard on top of one"
            % (s.bytes_of("sharded-by-doc", 64, scale),))
        assert s.bytes_of("two-tier", 1, scale) == two_tier, (
            "a two-tier index holds %r bytes, not the hot clauses' own %d"
            % (s.bytes_of("two-tier", 1, scale), two_tier))
        assert s.bytes_of("two-tier", 64, scale) == two_tier, (
            "a two-tier layout keeps every vector as it shards: %r"
            % (s.bytes_of("two-tier", 64, scale),))
        assert s.bytes_of("two-tier", 1, scale) < flat, (
            "a two-tier layout is not cheaper than a flat one: %r"
            % (s.bytes_of("two-tier", 1, scale),))
        _refuses(s.PlanError, "bytes_of with a layout it does not know",
                 lambda: s.bytes_of("flat-tier", 1, scale), names=("flat-tier",))
        _refuses(s.PlanError, "bytes_of with no shards",
                 lambda: s.bytes_of("flat", 0, scale), names=("0",))
        _refuses(s.PlanError, "bytes_of with a shard count that is a string",
                 lambda: s.bytes_of("flat", "2", scale), names=("2",))
        _refuses(s.PlanError, "an estate missing its numbers",
                 lambda: s.bytes_of("flat", 1, {"hot_bp": 1}), names=("clauses", "terms"))

    def _s2_scan_of(s, world):
        scale = world.SCALE
        hot = _s2_hot_scale()
        assert s.scan_of("flat", 1, scale) == 10000, (
            "a flat index scans %r basis points, not the whole estate"
            % (s.scan_of("flat", 1, scale),))
        assert s.scan_of("flat", 64, scale) == 10000, (
            "a flat index's scan moves with the shard count: %r"
            % (s.scan_of("flat", 64, scale),))
        assert s.scan_of("sharded-by-doc", 1, scale) == 10000, (
            "one shard scans %r basis points, not the whole estate"
            % (s.scan_of("sharded-by-doc", 1, scale),))
        assert s.scan_of("sharded-by-doc", 4, scale) == 2500, (
            "four shards scan %r basis points, not a quarter of the estate"
            % (s.scan_of("sharded-by-doc", 4, scale),))
        assert s.scan_of("sharded-by-doc", 8, scale) == 1250, (
            "eight shards scan %r basis points, not an eighth"
            % (s.scan_of("sharded-by-doc", 8, scale),))
        assert s.scan_of("sharded-by-doc", 64, scale) == 156, (
            "sixty-four shards scan %r basis points, and the estate divides to 156"
            % (s.scan_of("sharded-by-doc", 64, scale),))
        assert s.scan_of("two-tier", 1, scale) == 10000, (
            "a one-shard two-tier plan scans %r, not the whole estate over the hot tier"
            % (s.scan_of("two-tier", 1, scale),))
        assert s.scan_of("two-tier", 4, scale) == 2500, (
            "a four-shard two-tier plan scans %r, not a quarter of the estate"
            % (s.scan_of("two-tier", 4, scale),))
        assert s.scan_of("two-tier", 8, scale) == 2000, (
            "past the hot tier a two-tier plan scans %r, not the hot tier's own 2000"
            % (s.scan_of("two-tier", 8, scale),))
        assert s.scan_of("two-tier", 64, scale) == 2000, (
            "a two-tier plan sharded further forgot its hot tier: %r"
            % (s.scan_of("two-tier", 64, scale),))
        assert s.scan_of("two-tier", 4, hot) == 10000, (
            "an estate with every clause hot scans %r, not the whole hot tier"
            % (s.scan_of("two-tier", 4, hot),))
        _refuses(s.PlanError, "scan_of with a layout it does not know",
                 lambda: s.scan_of("shards", 1, scale), names=("shards",))
        _refuses(s.PlanError, "scan_of with no shards",
                 lambda: s.scan_of("two-tier", -1, scale), names=("-1",))
        _refuses(s.PlanError, "scan_of with an estate missing its numbers",
                 lambda: s.scan_of("two-tier", 1, {}), names=("clauses", "hot_bp"))

    def _s2_plan(s, world):
        scale = world.SCALE
        tiny = _s2_mb(6288000000)
        generous = tiny + 100
        fits = s.plan(scale, generous)
        assert tuple(fits) == S2_PLAN_KEYS, (
            "a plan's keys are %r, not %r" % (tuple(fits), S2_PLAN_KEYS))
        assert fits["verdict"] == "fits", (
            "a budget that buys a plan answered %r" % (fits["verdict"],))
        assert fits["problems"] == (), (
            "a plan that fits carries problems: %r" % (fits["problems"],))
        assert fits["layout"] == "two-tier", (
            "the cheapest plan that pays is %r, not the two-tier one" % (fits["layout"],))
        assert fits["shards"] == 4, (
            "the plan is cut into %r shards, and the fewest that scan within budget is 4"
            % (fits["shards"],))
        assert fits["memory_mb"] == tiny, (
            "the plan's memory is %r, not the two-tier estate's own %d"
            % (fits["memory_mb"], tiny))
        assert fits["scan_bp"] == 2500, (
            "the plan scans %r basis points, not exactly the budget's own 2500"
            % (fits["scan_bp"],))
        assert fits["memory_mb"] == _s2_mb(s.bytes_of(fits["layout"], fits["shards"], scale)), (
            "the plan's memory %r is not its own layout's bytes rounded up"
            % (fits["memory_mb"],))
        assert fits["memory_mb"] <= generous, (
            "a kept plan does not pay its budget: %r > %r" % (fits["memory_mb"], generous))
        assert fits["scan_bp"] <= s.SCAN_BUDGET_BP, (
            "a kept plan scans %r, past the budget" % (fits["scan_bp"],))
        assert fits["postings"] == scale["clauses"] * 4, (
            "the plan's postings are %r, not the estate's own %r"
            % (fits["postings"], scale["clauses"] * 4))
        assert fits["index_cents"] == 22400, (
            "indexing costs %r cents, not 40 cents a million postings on 560M postings"
            % (fits["index_cents"],))
        assert fits["query_cents"] == 2100, (
            "a query costs %r cents, not the scanned quarter of the estate"
            % (fits["query_cents"],))
        assert fits["query_cents"] != 8400, (
            "the query was priced on the whole estate: %r" % (fits["query_cents"],))

        exact = s.plan(scale, tiny)
        assert exact["verdict"] == "fits" and exact["memory_mb"] == tiny, (
            "a budget exactly the plan's memory was refused: %r" % (exact,))
        below = s.plan(scale, tiny - 1)
        assert below["verdict"] == "refused", (
            "a megabyte short of the memory still bought a plan: %r" % (below,))
        assert below["problems"] == (("over-budget", tiny), ("scan-too-wide", 10000)), (
            "the refusal's problems are %r, not the plan's own reasons in order"
            % (below["problems"],))

        refused = s.plan(scale, 1)
        assert refused["verdict"] == "refused", (
            "a budget no layout buys answered %r" % (refused["verdict"],))
        assert refused["layout"] == "two-tier" and refused["shards"] == 1, (
            "the refusal names %r sharded %r, not the smallest-memory plan"
            % (refused["layout"], refused["shards"]))
        assert refused["memory_mb"] == tiny, (
            "the refused plan's memory is %r, not the smallest %d" % (refused["memory_mb"], tiny))
        assert refused["problems"] == (("over-budget", tiny), ("scan-too-wide", 10000)), (
            "the refusal is %r, not both of the plan's own reasons with its own numbers"
            % (refused["problems"],))
        assert refused["problems"][0][1] != 1, (
            "the refusal named the budget rather than the plan's own number: %r"
            % (refused["problems"],))

        roomy = s.plan(scale, 1000000)
        assert roomy["layout"] == "two-tier" and roomy["memory_mb"] == tiny, (
            "a budget that buys everything still answered %r" % (roomy,))

        hot = _s2_hot_scale()
        fallback = s.plan(hot, 1)
        assert fallback["layout"] == "flat", (
            "a tie in memory is broken by LAYOUTS order, and %r came first"
            % (fallback["layout"],))
        assert fallback["shards"] == 1, (
            "a tie in memory and layout is broken by the fewest shards, not %r"
            % (fallback["shards"],))
        assert fallback["memory_mb"] == _s2_mb(13456000000), (
            "every-hot estate's smallest plan holds %r, not the flat estate's %d"
            % (fallback["memory_mb"], _s2_mb(13456000000)))
        broke = s.plan(hot, _s2_mb(13504000000))
        assert broke["verdict"] == "fits" and broke["layout"] == "sharded-by-doc", (
            "an every-hot estate buys %r, not the sharded layout that scans within budget"
            % (broke,))
        assert broke["shards"] == 4, (
            "the sharded plan is cut into %r shards, not the fewest 4" % (broke["shards"],))

        for row in (fits, exact, below, refused, roomy, fallback, broke):
            assert 1 <= row["shards"] <= s.MAX_SHARDS, (
                "a plan is cut into %r shards, past the cap %d"
                % (row["shards"], s.MAX_SHARDS))
            assert row["scan_bp"] > 0, ("a plan scans %r basis points" % (row["scan_bp"],))

        _refuses(s.PlanError, "a plan with no budget",
                 lambda: s.plan(scale, 0), names=("budget",))
        _refuses(s.PlanError, "a plan with a negative budget",
                 lambda: s.plan(scale, -1), names=("budget",))
        _refuses(s.PlanError, "a plan with a budget that is not a whole number",
                 lambda: s.plan(scale, "64"), names=("budget",))
        _refuses(s.PlanError, "an estate missing its numbers",
                 lambda: s.plan({"documents": 1}, 64), names=("clauses", "terms"))
        _refuses(s.PlanError, "an estate that is not a mapping",
                 lambda: s.plan(7, 64), names=("int",))

    def _s2_explain(s, world):
        scale = world.SCALE
        plan = s.plan(scale, _s2_mb(6288000000) + 100)
        claims = s.explain(plan)
        assert tuple(name for name, _ in claims) == S2_CLAIMS, (
            "explain's claims are %r, not %r" % (tuple(name for name, _ in claims),
                                                 S2_CLAIMS))
        claims = dict(claims)
        assert claims["layout"] == plan["layout"], (
            "explain claims the layout %r, and the plan says %r"
            % (claims["layout"], plan["layout"]))
        assert claims["shards"] == plan["shards"], (
            "explain claims %r shards, and the plan says %r"
            % (claims["shards"], plan["shards"]))
        assert claims["postings"] == plan["postings"], (
            "explain claims %r postings, and the plan says %r"
            % (claims["postings"], plan["postings"]))
        assert claims["memory_mb"] == plan["memory_mb"], (
            "explain claims %r megabytes, and the plan says %r"
            % (claims["memory_mb"], plan["memory_mb"]))
        assert claims["scan_bp"] == plan["scan_bp"], (
            "explain claims a %r basis-point scan, and the plan says %r"
            % (claims["scan_bp"], plan["scan_bp"]))
        assert claims["clauses-scanned"] == scale["clauses"] * plan["scan_bp"] // 10000, (
            "explain claims %r clauses scanned, not the plan's scanned share %r"
            % (claims["clauses-scanned"], scale["clauses"] * plan["scan_bp"] // 10000))
        assert claims["clauses-scanned"] == 35000000, (
            "a quarter of the estate is %r clauses, not 35000000"
            % (claims["clauses-scanned"],))
        assert claims["index_cents"] == plan["index_cents"] == 22400, (
            "explain claims %r cents to index, and 560M postings at 40 cents a million "
            "is 22400" % (claims["index_cents"],))
        assert claims["query_cents"] == plan["query_cents"] == 2100, (
            "explain claims %r cents a query, not the plan's own 2100"
            % (claims["query_cents"],))
        _refuses(s.PlanError, "a plan that cannot be explained",
                 lambda: s.explain({"layout": "flat"}), names=("shards",))
        _refuses(s.PlanError, "an explanation of something that is not a plan",
                 lambda: s.explain(("flat",)), names=("tuple",))

    def _s2_ledger(s, world):
        corpus = world
        library = corpus.Corpus.build(7)
        before = library.stats()
        _s2_workload(s, world)
        after = library.stats()
        assert after == before, (
            "a plan of numbers asked the customer's library something, so its log moved: "
            "%r then %r" % (before, after))
        for key in S2_COUNTERS:
            assert after[key] == 0, (
                "a plan of numbers asked the customer's library to %s: %r" % (key, after))
        assert after["documents"] == len(library.documents), (
            "the library recounts %r documents and holds %r"
            % (after["documents"], len(library.documents)))
        index = tuple(library.clause_index(record["doc"]) for record in library.documents)
        assert after["clauses"] == sum(len(clauses) for clauses in index), (
            "the library recounts %r clauses, and its own index holds %d"
            % (after["clauses"], sum(len(clauses) for clauses in index)))

    def _s2_twice(s, world):
        one = _s2_workload(s, world)
        two = _s2_workload(s, world)
        assert one == two, (
            "two runs of one estate planned differently, so a plan is not a function of "
            "its inputs")

    import stage_02 as s
    import corpus as world
    _s2_constants(s, world)
    _s2_weigh(s, world)
    _s2_bytes_of(s, world)
    _s2_scan_of(s, world)
    _s2_plan(s, world)
    _s2_explain(s, world)
    _s2_ledger(s, world)
    _s2_twice(s, world)

# --- stage 3 -----------------------------------------------------------------------
def check_3():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "agentic-retrieval-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("K1_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "course.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set K1_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked
        against the message: an exception of the right family raised for the wrong
        reason is not the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return refused
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _chunk_id(chunk):
        return "%s:%s" % (chunk["doc"], chunk["clause"])

    def _chunks_of(one, c):
        """The check's own chunk list: stage 1's chunker over every document, in order."""
        chunks = []
        for document in c.documents:
            parsed, _problems = one.chunk(document)
            chunks.extend(parsed)
        return chunks

    def _want_rank(hits, limit):
        """Score descending, ties by chunk id ascending, one entry per chunk id."""
        ordered = sorted(hits, key=lambda hit: (-hit["score"], hit["chunk"]))
        kept = []
        seen = set()
        for hit in ordered:
            if hit["chunk"] not in seen:
                seen.add(hit["chunk"])
                kept.append(hit)
        return tuple(kept[:limit])

    def _want_bm25(c, chunks, query, limit):
        """The contract's BM25, recomputed here from the corpus's own analyzer."""
        counts = []
        lengths = []
        places = {}
        for position, chunk in enumerate(chunks):
            tally = {}
            for token in c.terms(chunk["text"]):
                tally[token] = tally.get(token, 0) + 1
            counts.append(tally)
            lengths.append(sum(tally.values()))
            for token in tally:
                places.setdefault(token, []).append(position)
        average = max(1, sum(lengths) // len(chunks))
        wanted = []
        for term in c.terms(query):
            if term not in wanted:
                wanted.append(term)
        held = {}
        for term in wanted:
            for position in places.get(term, ()):
                tf = counts[position][term]
                idf = c.idf(term)
                numerator = idf * tf * (120 + 10000) * 10000
                denominator = tf * 10000 + 120 * (10000 - 75
                                                  + 75 * lengths[position] * 10000
                                                  // average)
                held.setdefault(position, {})[term] = numerator // denominator // 10000
        hits = []
        for position in held:
            pairs = tuple(sorted(held[position].items()))
            hits.append({"chunk": _chunk_id(chunks[position]),
                         "score": sum(value for _, value in pairs), "why": pairs})
        return _want_rank(hits, limit)

    def _want_scale(c, chunk):
        """The world's vector scale squared, read off a vector the world answered."""
        return sum(value * value for value in c.embed(chunk["text"]))

    def _want_dense(c, chunks, query, limit):
        """The contract's dense scorer, recomputed here from the corpus's own embedder."""
        vector = c.embed(query)
        scale = _want_scale(c, chunks[0])
        hits = []
        for chunk in chunks:
            chunk_vector = c.embed(chunk["text"])
            dot = sum(a * b for a, b in zip(vector, chunk_vector))
            hits.append({"chunk": _chunk_id(chunk), "score": dot // 100,
                         "why": (("dot", dot), ("scale", scale))})
        return _want_rank(hits, limit)

    def _want_fuse(lexical, dense, limit):
        """The contract's reciprocal rank fusion, recomputed from two rankings."""
        ranks = {"dense": {}, "lexical": {}}
        for name, hits in (("lexical", lexical), ("dense", dense)):
            for rank, hit in enumerate(hits, start=1):
                ranks[name].setdefault(hit["chunk"], rank)
        order = list(dict.fromkeys([hit["chunk"] for hit in lexical]
                                   + [hit["chunk"] for hit in dense]))
        hits = []
        for identify in order:
            here = (ranks["dense"].get(identify, 0), ranks["lexical"].get(identify, 0))
            score = sum(10000 // (60 + rank) for rank in here if rank)
            hits.append({"chunk": identify, "score": score,
                         "why": (("dense", here[0]), ("lexical", here[1]),
                                 ("rrf", score))})
        return _want_rank(hits, limit)

    def _want_search(c, chunks, query, limit, mode):
        """The ranking the check's own scorers give `mode` for one query."""
        if mode == "lexical":
            return _want_bm25(c, chunks, query, limit)
        if mode == "dense":
            return _want_dense(c, chunks, query, limit)
        return _want_fuse(_want_bm25(c, chunks, query, limit),
                          _want_dense(c, chunks, query, limit), limit)

    def _want_measure(c, chunks, questions, limit, mode):
        """The contract's measurement, recomputed here from the check's own scorers."""
        answered = 0
        expected_total = 0
        found_total = 0
        missed = []
        for question in questions:
            expected = tuple(question["expected"])
            found = set(hit["chunk"]
                        for hit in _want_search(c, chunks, question["text"], limit, mode))
            present = [clause for clause in expected if clause in found]
            expected_total = expected_total + len(expected)
            found_total = found_total + len(present)
            if len(present) == len(expected):
                answered = answered + 1
            else:
                missed.append(question["qid"])
        if expected_total:
            hit_bp = 10000 * found_total // expected_total
        else:
            hit_bp = 0
        return {"mode": mode, "answered": answered, "hit_bp": hit_bp,
                "missed": tuple(sorted(missed))}

    def _want_pick(rows):
        """The best mode and the verdict the contract's rule gives these three rows."""
        order = sorted(rows, key=lambda row: (-row["hit_bp"], -row["answered"],
                                              ("lexical", "dense", "hybrid")
                                              .index(row["mode"])))
        best = order[0]
        runner_up = order[1]
        if best["hit_bp"] - runner_up["hit_bp"] < 100:
            return best["mode"], "no-difference"
        return best["mode"], best["mode"]

    def _s3_gap(rows):
        """The distance between the best two of three rows, under the contract's order."""
        order = sorted(rows, key=lambda row: (-row["hit_bp"], -row["answered"],
                                              ("lexical", "dense", "hybrid")
                                              .index(row["mode"])))
        return order[0]["hit_bp"] - order[1]["hit_bp"]

    def _s3_constants(s):
        assert tuple(s.HIT_KEYS) == ("chunk", "score", "why"), (
            "a hit is the chunk, the score and the arithmetic that made it, in that order, "
            "and HIT_KEYS was %r" % (tuple(s.HIT_KEYS),))
        assert tuple(s.MEASURE_KEYS) == ("mode", "answered", "hit_bp", "missed"), (
            "a measurement is its mode, its answered count, its hit_bp and its missed "
            "qids, in that order, and MEASURE_KEYS was %r" % (tuple(s.MEASURE_KEYS),))
        assert tuple(s.SEARCH_MODES) == ("lexical", "dense", "hybrid"), (
            "the three modes are lexical, dense and hybrid, the order every row is "
            "printed in, and SEARCH_MODES was %r" % (tuple(s.SEARCH_MODES),))
        assert s.BM25_K1_BP == 120, (
            "BM25's k1 is one and two tenths, written as 120 basis points, and "
            "BM25_K1_BP was %r" % (s.BM25_K1_BP,))
        assert s.BM25_B_BP == 75, (
            "BM25's b is three quarters, written as 75 basis points, and BM25_B_BP was %r"
            % (s.BM25_B_BP,))
        assert s.RRF_K == 60, (
            "the reciprocal rank constant is 60, and RRF_K was %r" % (s.RRF_K,))
        assert s.SCORE_SCALE == 10000, (
            "a whole score is 10000 in this course, and SCORE_SCALE was %r"
            % (s.SCORE_SCALE,))
        assert s.NO_DIFFERENCE_BP == 100, (
            "two modes within 100 basis points are the same mode, and NO_DIFFERENCE_BP "
            "was %r" % (s.NO_DIFFERENCE_BP,))

    def _s3_build(s, one, c):
        before = c.stats()
        assert before["analyses"] == 0 and before["embeds"] == 0, (
            "a corpus that has been built and asked nothing logs nothing, and it was %r"
            % (before,))
        index = s.Index.build(c)
        after = c.stats()
        chunks = _chunks_of(one, c)
        assert tuple(index.chunks) == tuple(chunks), (
            "the index chunks every document with stage 1, in document order, and it held "
            "%r chunks" % (len(tuple(index.chunks)),))
        assert tuple(one.chunk_id(chunk) for chunk in index.chunks) == tuple(
            _chunk_id(chunk) for chunk in chunks), (
            "every chunk the index holds keeps stage 1's own id, and one did not")
        analysis = index.analysis()
        assert tuple(analysis) == ("chunks", "terms", "postings", "embeds", "corpus_asks"), (
            "analysis() recounts chunks, terms, postings, embeds and corpus_asks in that "
            "order, and it was %r" % (tuple(analysis),))
        assert analysis["chunks"] == after["clauses"], (
            "the index holds a record for every clause of the corpus, and it held %r of %r"
            % (analysis["chunks"], after["clauses"]))
        assert analysis["chunks"] == len(chunks), (
            "the index holds every chunk stage 1 made, and it held %r of %r"
            % (analysis["chunks"], len(chunks)))
        assert after["analyses"] == analysis["chunks"], (
            "a chunk is analyzed once while the index is built, and the corpus recounted "
            "%r analyses for %r chunks" % (after["analyses"], analysis["chunks"]))
        assert after["embeds"] == analysis["chunks"], (
            "a chunk is embedded once while the index is built, and the corpus recounted "
            "%r embeds for %r chunks" % (after["embeds"], analysis["chunks"]))
        assert analysis["corpus_asks"] == after["analyses"] + after["embeds"], (
            "corpus_asks counts the analyses and the embeddings the index asked for, and "
            "it was %r against %r" % (analysis["corpus_asks"],
                                      after["analyses"] + after["embeds"]))
        terms = set()
        postings = 0
        for chunk in chunks:
            tokens = set(c.terms(chunk["text"]))
            terms.update(tokens)
            postings += len(tokens)
        assert analysis["terms"] == len(terms), (
            "analysis() counts the index's own distinct terms, and it said %r where the "
            "chunks hold %r" % (analysis["terms"], len(terms)))
        assert analysis["postings"] == postings, (
            "analysis() counts one posting per term per chunk, and it said %r where the "
            "chunks hold %r" % (analysis["postings"], postings))
        first = set()
        for chunk in chunks:
            identify = one.chunk_id(chunk)
            held = index.of(identify)
            assert held is not None, (
                "the index resolves every chunk it holds, and it did not resolve %r"
                % (identify,))
            if identify not in first:
                first.add(identify)
                assert held == chunk, (
                    "of() answers the first chunk of an id the corpus prints twice, and "
                    "%r came back as %r" % (identify, held))
        assert index.of("nope-9:1.") is None, (
            "of() answers None for a chunk the index does not hold, and it answered %r"
            % (index.of("nope-9:1."),))
        assert index.corpus is c, (
            "the index answers the corpus it was built from, and it answered %r"
            % (index.corpus,))
        return index, chunks

    def _s3_lexical(s, c, chunks, index):
        query = c.questions[0]["text"]
        hits = s.bm25(index, query, 5)
        assert hits == index.lexical(query, 5), (
            "Index.lexical is the same BM25 over the index's own chunks, and the two "
            "answered differently")
        assert hits == _want_bm25(c, chunks, query, 5), (
            "the lexical ranking is not the contract's BM25, and it was %r" % (hits,))
        assert len(hits) <= 5, (
            "a ranking is cut to the limit, and %r hits came back" % (len(hits),))
        for hit in hits:
            assert tuple(hit) == tuple(s.HIT_KEYS), (
                "a hit is its three fields in order, and it was %r" % (tuple(hit),))
            assert index.of(hit["chunk"]) is not None, (
                "every hit names a chunk the index holds, and %r is not one" % (hit["chunk"],))
            assert hit["score"] == sum(value for _, value in hit["why"]), (
                "a lexical score is the sum of its own why, and %r was not" % (hit,))
            names = [name for name, _ in hit["why"]]
            assert names == sorted(names), (
                "a hit's why is sorted by term, and %r was not" % (names,))
        scores = [hit["score"] for hit in hits]
        assert scores == sorted(scores, reverse=True), (
            "a lexical ranking is by score descending, and its scores were %r" % (scores,))
        whole = s.bm25(index, query, len(chunks) + 5)
        assert whole == _want_bm25(c, chunks, query, len(chunks) + 5), (
            "a limit past the chunk count still answers the contract's BM25, and it "
            "answered %r" % (whole,))
        ids = [hit["chunk"] for hit in whole]
        assert len(ids) == len(set(ids)), (
            "a ranking holds one entry per chunk id, and it held %r" % (ids,))
        assert s.bm25(index, "", 5) == (), (
            "a query with no terms scores no chunk, and it answered %r"
            % (s.bm25(index, "", 5),))
        assert s.bm25(index, "zzzznotaterm", 5) == (), (
            "a query term no chunk holds contributes nothing rather than raising, and it "
            "answered %r" % (s.bm25(index, "zzzznotaterm", 5),))

    def _s3_dense(s, c, chunks, index):
        query = c.questions[0]["text"]
        hits = s.dense(index, query, 5)
        assert hits == index.dense(query, 5), (
            "Index.dense is the same scorer over the index's own chunks, and the two "
            "answered differently")
        assert hits == _want_dense(c, chunks, query, 5), (
            "the dense ranking is not the contract's dot product, and it was %r" % (hits,))
        for hit in hits:
            assert tuple(hit) == tuple(s.HIT_KEYS), (
                "a hit is its three fields in order, and it was %r" % (tuple(hit),))
            why = dict(hit["why"])
            assert sorted(why) == ["dot", "scale"], (
                "a dense hit explains itself with its dot and the scale it is read in, "
                "and its why was %r" % (hit["why"],))
            assert hit["score"] == why["dot"] // 100, (
                "a dense score is the dot product divided by the scale's fixed point, and "
                "%r was not" % (hit,))
            assert why["scale"] == _want_scale(c, chunks[0]), (
                "the scale a dense hit records is the square of the world's own vector "
                "scale, and it was %r" % (why["scale"],))
        whole = s.dense(index, query, len(chunks) + 5)
        assert len(whole) == len(set(_chunk_id(chunk) for chunk in chunks)), (
            "every chunk scores in a dense ranking, and %r of %r came back"
            % (len(whole), len(chunks)))
        scores = [hit["score"] for hit in whole]
        assert scores == sorted(scores, reverse=True), (
            "a dense ranking is by score descending, and its scores were %r" % (scores,))
        assert whole == _want_dense(c, chunks, query, len(chunks) + 5), (
            "the whole dense ranking is not the contract's dot product, and it was %r"
            % (whole,))

    def _s3_fuse(s, c, chunks, index):
        query = c.questions[0]["text"]
        lexical = s.bm25(index, query, 7)
        dense = s.dense(index, query, 7)
        fused = s.fuse(lexical, dense, 7)
        assert fused == index.fused(query, 7), (
            "Index.fused is the fusion of this index's own two rankings, and the two "
            "answered differently")
        assert fused == s.search(index, query, 7, "hybrid"), (
            "search(..., \"hybrid\") is the fusion of the two rankings, and it was not")
        assert fused == _want_fuse(lexical, dense, 7), (
            "the fused ranking is not the contract's reciprocal rank fusion, and it was "
            "%r" % (fused,))
        for hit in fused:
            assert tuple(hit) == tuple(s.HIT_KEYS), (
                "a hit is its three fields in order, and it was %r" % (tuple(hit),))
            names = [name for name, _ in hit["why"]]
            assert names == ["dense", "lexical", "rrf"], (
                "a fused hit records both ranks and their sum, sorted by name, and it was "
                "%r" % (hit["why"],))
            values = dict(hit["why"])
            want = 0
            for name in ("dense", "lexical"):
                if values[name]:
                    want += 10000 // (60 + values[name])
            assert hit["score"] == want and values["rrf"] == want, (
                "a fused score is the sum of the reciprocal ranks it appears at, and %r "
                "was not %r" % (hit, want))
        first = ({"chunk": "z:1.", "score": 5, "why": ()},
                 {"chunk": "b:2.", "score": 4, "why": ()})
        second = ({"chunk": "a:1.", "score": 9, "why": ()},
                  {"chunk": "b:2.", "score": 8, "why": ()})
        made = s.fuse(first, second, 5)
        assert tuple(hit["chunk"] for hit in made) == ("b:2.", "a:1.", "z:1."), (
            "a chunk in both lists outranks a chunk in one, a tie goes by chunk id, and "
            "the fusion was %r" % (tuple(hit["chunk"] for hit in made),))
        assert made[0]["score"] == 10000 // 62 + 10000 // 62, (
            "a chunk at rank two in both lists scores its two reciprocal ranks, and it "
            "scored %r" % (made[0]["score"],))
        assert dict(made[0]["why"]) == {"dense": 2, "lexical": 2, "rrf": made[0]["score"]}, (
            "a chunk in one list only records a zero for the list it is absent from, and "
            "%r did not" % (made[0]["why"],))
        assert made[1]["score"] == 10000 // 61, (
            "a chunk at rank one in one list scores that single reciprocal rank, and it "
            "scored %r" % (made[1]["score"],))

    def _s3_search(s, c, chunks, index):
        query = c.questions[0]["text"]
        assert s.search(index, query, 4, "lexical") == s.bm25(index, query, 4), (
            "search on \"lexical\" is bm25 over the index, and it was not")
        assert s.search(index, query, 4, "dense") == s.dense(index, query, 4), (
            "search on \"dense\" is dense over the index, and it was not")
        before = c.stats()
        _refuses(ValueError, "a mode that is not one of the three",
                 lambda: s.search(index, query, 4, "semantic"), names=("semantic",))
        assert c.stats() == before, (
            "a refused search asked the corpus anyway: %r" % (c.stats(),))

    def _s3_measure(s, c, chunks, index):
        for mode in ("lexical", "dense", "hybrid"):
            got = s.measure(index, c.questions, 5, mode)
            assert tuple(got) == tuple(s.MEASURE_KEYS), (
                "a measurement is its four fields in order, and it was %r" % (tuple(got),))
            assert got["mode"] == mode, (
                "a measurement names the mode it measured, and it said %r" % (got["mode"],))
            assert got == _want_measure(c, chunks, c.questions, 5, mode), (
                "the %s measurement is not the contract's, and it was %r" % (mode, got))
            assert 0 <= got["hit_bp"] <= 10000, (
                "a share is basis points, and it was %r" % (got["hit_bp"],))
            assert got["answered"] <= len(c.questions), (
                "answered counts questions, and it was %r" % (got["answered"],))
            assert got["missed"] == tuple(sorted(got["missed"])), (
                "missed is a sorted tuple of qids, and it was %r" % (got["missed"],))
            assert set(got["missed"]) <= set(question["qid"] for question in c.questions), (
                "missed names qids of the questions it was given, and it named %r"
                % (got["missed"],))
        assert s.measure(index, (), 5, "hybrid") == {
            "mode": "hybrid", "answered": 0, "hit_bp": 0, "missed": ()}, (
            "measuring no questions answers nothing rather than raising, and it answered "
            "%r" % (s.measure(index, (), 5, "hybrid"),))

    def _s3_pick(s, c, chunks, index):
        picked = s.pick(index, c.questions, 5)
        assert tuple(picked) == ("best", "rows", "verdict"), (
            "pick answers best, rows and verdict in that order, and it was %r"
            % (tuple(picked),))
        assert tuple(row["mode"] for row in picked["rows"]) == tuple(s.SEARCH_MODES), (
            "pick answers one row per mode in SEARCH_MODES order, and it was %r"
            % (tuple(row["mode"] for row in picked["rows"]),))
        rows = tuple(_want_measure(c, chunks, c.questions, 5, mode)
                     for mode in s.SEARCH_MODES)
        assert picked["rows"] == rows, (
            "pick's rows are the three measurements, and they were %r" % (picked["rows"],))
        best, verdict = _want_pick(rows)
        assert picked["best"] == best, (
            "the best mode is the highest hit_bp, ties by answered and then by mode "
            "order, and it was %r not %r" % (picked["best"], best))
        assert picked["verdict"] == verdict, (
            "the verdict is no-difference inside the noise bound and the best mode "
            "outside it, and it was %r not %r" % (picked["verdict"], verdict))

    def _s3_boundary(s, c, chunks, index):
        """Both sides of the noise bound, over the customer's own labelled questions."""
        earned = None
        noise = None
        for limit in range(1, len(chunks) + 1):
            rows = tuple(s.measure(index, c.questions, limit, mode)
                         for mode in s.SEARCH_MODES)
            picked = s.pick(index, c.questions, limit)
            want_best, want_verdict = _want_pick(rows)
            assert picked["best"] == want_best and picked["verdict"] == want_verdict, (
                "at limit %d pick answered (%r, %r) where its own rows say (%r, %r)"
                % (limit, picked["best"], picked["verdict"], want_best, want_verdict))
            gap = _s3_gap(rows)
            if gap >= s.NO_DIFFERENCE_BP and earned is None:
                assert want_verdict == want_best, (
                    "a gap of %r at or above the noise bound is a real difference, and "
                    "it answered no-difference" % (gap,))
                earned = limit
            if gap < s.NO_DIFFERENCE_BP and noise is None:
                assert want_verdict == "no-difference", (
                    "a gap of %r inside the noise bound is no difference, and it named %r"
                    % (gap, want_verdict))
                noise = limit
            if earned is not None and noise is not None:
                break
        assert earned is not None, (
            "the customer's own questions never separate two modes by NO_DIFFERENCE_BP, "
            "so the noise bound's far side is unreachable")
        assert noise is not None, (
            "the customer's own questions never leave two modes inside the noise bound, "
            "so the bound's near side is unreachable")
        return earned, noise

    def _toy_document(count):
        """One document whose every clause carries its own unique word."""
        lines = []
        for number in range(1, count + 1):
            lines.append("%d.1 w%d" % (number, number))
        return {"doc": "toy-1", "title": "Toy Agreement", "version": 1,
                "superseded_by": None, "text": "\n".join(lines) + "\n"}

    def _toy_corpus(world, count, expected):
        """A corpus the check builds itself, so its labels are the check's own."""
        questions = []
        for number in range(1, count + 1):
            questions.append({"qid": "t-%03d" % number, "text": "about w%d" % number,
                              "expected": expected(number), "conversation": ()})
        return world.Corpus((_toy_document(count),), tuple(questions),
                            {"TOY": "toy agreement"}, ())

    def _s3_toy_exact(s, world):
        """A unique word per clause makes the lexical side of the fixture exact."""
        count = 100
        c = _toy_corpus(world, count, lambda number: ("toy-1:%d.1" % number,))
        index = s.Index.build(c)
        analysis = index.analysis()
        assert analysis["chunks"] == count and analysis["embeds"] == count, (
            "the index holds one chunk per clause of the fixture, and it said %r"
            % (analysis,))
        lexical = s.measure(index, c.questions, 1, "lexical")
        assert lexical == {"mode": "lexical", "answered": count, "hit_bp": 10000,
                           "missed": ()}, (
            "a unique word retrieves its own clause every time, and the lexical "
            "measurement was %r" % (lexical,))
        picked = s.pick(index, c.questions, 1)
        rows = tuple(row["hit_bp"] for row in picked["rows"])
        assert max(rows) - sorted(rows)[-2] >= s.NO_DIFFERENCE_BP, (
            "the fixture is meant to leave two modes apart by the noise bound, and its "
            "hit_bp rows were %r" % (rows,))
        assert picked["best"] == "lexical", (
            "the mode that retrieved everything is the best one, and pick named %r"
            % (picked["best"],))
        assert picked["verdict"] == "lexical", (
            "a gap at or above the noise bound names the best mode, and the verdict was "
            "%r" % (picked["verdict"],))

    def _s3_toy_partial(s, world):
        """One of two expected ids is not answered, and the share says so."""
        c = _toy_corpus(world, 2, lambda number: (("toy-1:1.1", "toy-1:2.1")
                                                  if number == 1 else ("toy-1:2.1",)))
        index = s.Index.build(c)
        got = s.measure(index, c.questions, 1, "lexical")
        assert got == {"mode": "lexical", "answered": 1, "hit_bp": 6666,
                       "missed": ("t-001",)}, (
            "a question whose every expected id must come back is not answered when only "
            "one of two does, and the measurement was %r" % (got,))

    def _s3_missed_order(s, world):
        """The qids are sorted on their own, not left in the order they were asked."""
        questions = []
        for qid in ("t-003", "t-001", "t-002"):
            questions.append({"qid": qid, "text": "about w3",
                              "expected": ("toy-1:2.1",), "conversation": ()})
        c = world.Corpus((_toy_document(3),), tuple(questions),
                         {"TOY": "toy agreement"}, ())
        index = s.Index.build(c)
        got = s.measure(index, c.questions, 1, "lexical")
        assert got == {"mode": "lexical", "answered": 0, "hit_bp": 0,
                       "missed": ("t-001", "t-002", "t-003")}, (
            "the missed qids are sorted rather than left in the order they were asked, "
            "and the measurement was %r" % (got,))

    def _s3_toy_noise(s, world):
        """Nothing expected: three modes that cannot differ, and the tie-break."""
        c = _toy_corpus(world, 3, lambda number: ())
        index = s.Index.build(c)
        picked = s.pick(index, c.questions, 1)
        assert tuple(row["hit_bp"] for row in picked["rows"]) == (0, 0, 0), (
            "a question with nothing expected can miss nothing, and the rows were %r"
            % (picked["rows"],))
        assert tuple(row["answered"] for row in picked["rows"]) == (3, 3, 3), (
            "every question is answered when nothing is expected, and the rows were %r"
            % (picked["rows"],))
        assert picked["verdict"] == "no-difference", (
            "three modes that cannot differ are no difference, and the verdict was %r"
            % (picked["verdict"],))
        assert picked["best"] == "lexical", (
            "a three-way tie falls back on the modes' own order, and pick named %r"
            % (picked["best"],))

    def _s3_twice(s, world):
        def workload():
            c = world.Corpus.build(7)
            index = s.Index.build(c)
            query = c.questions[0]["text"]
            return (tuple(index.chunks),
                    s.bm25(index, query, 5), s.dense(index, query, 5),
                    s.search(index, query, 5, "hybrid"),
                    s.measure(index, c.questions, 5, "lexical"),
                    s.measure(index, c.questions, 5, "dense"),
                    s.measure(index, c.questions, 5, "hybrid"),
                    s.pick(index, c.questions, 5), index.analysis())
        assert workload() == workload(), (
            "two runs of one workload answered differently, so a run is not a function of "
            "its inputs")

    import corpus as world
    import stage_01 as one
    import stage_03 as s
    _s3_constants(s)
    c = world.Corpus.build(7)
    index, chunks = _s3_build(s, one, c)
    _s3_lexical(s, c, chunks, index)
    _s3_dense(s, c, chunks, index)
    _s3_fuse(s, c, chunks, index)
    _s3_search(s, c, chunks, index)
    _s3_measure(s, c, chunks, index)
    _s3_pick(s, c, chunks, index)
    _s3_boundary(s, c, chunks, index)
    _s3_toy_exact(s, world)
    _s3_toy_partial(s, world)
    _s3_missed_order(s, world)
    _s3_toy_noise(s, world)
    _s3_twice(s, world)

# --- stage 4 -----------------------------------------------------------------------
def check_4():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "agentic-retrieval-from-scratch"

    S4_RERANK_KEYS = ("chunk", "score", "signals")

    S4_COMPARE_KEYS = ("before", "after", "delta_bp", "verdict")

    S4_COVERAGE_WEIGHT = 3

    S4_PROXIMITY_WEIGHT = 2

    S4_WEIGHT_TOTAL = 5

    S4_PROXIMITY_WINDOW = 12

    S4_LEVEL_BONUS_BP = 500

    S4_NOISE_BP = 200

    S4_WHOLE_BP = 10000

    S4_SIGNALS = ("coverage", "level-bonus", "proximity")

    S4_VOCABULARY = ("earned", "within-noise", "hurt")

    def _repo(start=None):
        for candidate_start in (os.environ.get("K1_REPO"), os.environ.get("FDE_REPO"),
                                start, os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if (os.path.isfile(os.path.join(candidate, COURSE, "course.py"))
                        or os.path.isfile(os.path.join(candidate, COURSE, "corpus.py"))):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set K1_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked
        against the message: an exception of the right family raised for the wrong
        reason is not the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return refused
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _s4_id(chunk):
        """The chunk id of a chunk record, the way stage 1 spells it."""
        return "%s:%s" % (chunk["doc"], chunk["clause"])

    def _s4_count(retrieved, questions):
        """The check's own counting, by stage 3's answered/hit_bp/missed rules."""
        answered = 0
        covered = 0
        total = 0
        missed = []
        for question, found in zip(questions, retrieved):
            expected = tuple(question["expected"])
            total += len(expected)
            here = sum(1 for wanted in expected if wanted in found)
            covered += here
            if here == len(expected):
                answered += 1
            else:
                missed.append(question["qid"])
        return {"mode": "hybrid", "answered": answered,
                "hit_bp": 0 if total == 0 else covered * S4_WHOLE_BP // total,
                "missed": tuple(sorted(missed))}

    def _s4_places(terms):
        """Every term's positions in one token list."""
        places = {}
        for place, term in enumerate(terms):
            places.setdefault(term, []).append(place)
        return places

    def _s4_span(places, one, other):
        """The least distance between an occurrence of `one` and one of `other`."""
        near = None
        for left in places[one]:
            for right in places[other]:
                span = left - right if left > right else right - left
                if near is None or span < near:
                    near = span
        return near

    def _s4_window(library, chunks, window):
        """A chunk with two distinct terms `window` apart, and one a step beyond it."""
        inside = outside = None
        for chunk in chunks:
            places = _s4_places(library.terms(chunk["text"]))
            names = sorted(places)
            for index, one in enumerate(names):
                for other in names[index + 1:]:
                    span = _s4_span(places, one, other)
                    if span == window and inside is None:
                        inside = (chunk, one, other)
                    if span == window + 1 and outside is None:
                        outside = (chunk, one, other)
        return inside, outside

    def _s4_repeat(library, chunks, window):
        """A chunk and one term it repeats inside the window of itself."""
        for chunk in chunks:
            places = _s4_places(library.terms(chunk["text"]))
            for term in sorted(places):
                spots = places[term]
                for index in range(len(spots) - 1):
                    if spots[index + 1] - spots[index] <= window:
                        return chunk, term
        return None, None

    def _s4_pair(chunks, level):
        """Two chunks of one level, the larger id first — one certain tie, in reverse order."""
        same = sorted(_s4_id(chunk) for chunk in chunks if chunk["level"] == level)
        assert len(same) >= 2, (
            "the corpus has fewer than two level %d clauses, so a tie cannot be built" % (level,))
        return same[-1], same[0]

    def _s4_flip(s, three, index, library):
        """A query text whose front hit the fusion and the reranker disagree about."""
        texts = [question["text"] for question in library.questions]
        for chunk in index.chunks:
            texts.append(chunk["text"])
            texts.append(" ".join(library.terms(chunk["text"])[:4]))
        for text in texts:
            before = three.search(index, text, 1, "hybrid")
            if len(before) != 1:
                continue
            candidates = three.search(index, text, len(index.chunks), "hybrid")
            ranked = s.rerank(index, text, candidates, 1)
            if len(ranked) == 1 and ranked[0]["chunk"] != before[0]["chunk"]:
                return text, before[0]["chunk"], ranked[0]["chunk"]
        raise AssertionError(
            "no query in this corpus moves the front hit when it is reranked, so the "
            "reranker this stage measures never changes what the customer sees")

    def _s4_one(s, index, chunk_id, query, limit=5):
        """The stage's answer for one lone hit, which is what a signal fixture needs."""
        ranked = s.rerank(index, query, [{"chunk": chunk_id, "score": 0, "why": ()}], limit)
        assert len(ranked) == 1, (
            "a rerank of one hit answered %d hits, not one" % (len(ranked),))
        return ranked[0]

    def _s4_bonus(chunk):
        """The level bonus the contract pays this chunk."""
        return S4_LEVEL_BONUS_BP if chunk["level"] == 1 else 0

    def _s4_score(record):
        """The score recomputed from the record's own signals, by the pinned formula."""
        values = dict(record["signals"])
        return (values["coverage"] * S4_COVERAGE_WEIGHT // S4_WEIGHT_TOTAL
                + values["proximity"] * S4_PROXIMITY_WEIGHT // S4_WEIGHT_TOTAL
                + values["level-bonus"])

    def _s4_checked(record):
        """One reranked hit, checked as a record whose score is its own signals."""
        assert tuple(record) == S4_RERANK_KEYS, (
            "a reranked hit is %r, not %r" % (tuple(record), S4_RERANK_KEYS))
        assert tuple(name for name, value in record["signals"]) == S4_SIGNALS, (
            "the signals of %r are %r, not %r sorted by name"
            % (record["chunk"], tuple(record["signals"]), S4_SIGNALS))
        for name, value in record["signals"]:
            assert isinstance(value, int) and not isinstance(value, bool), (
                "the %s signal of %r is %r, not an int" % (name, record["chunk"], value))
        assert record["score"] == _s4_score(record), (
            "the score of %r is %r, which is not the sum of its own signals %r"
            % (record["chunk"], record["score"], record["signals"]))
        return record

    def _s4_constants(s):
        assert tuple(s.RERANK_KEYS) == S4_RERANK_KEYS, (
            "a reranked hit is %r, not %r" % (tuple(s.RERANK_KEYS), S4_RERANK_KEYS))
        assert tuple(s.COMPARE_KEYS) == S4_COMPARE_KEYS, (
            "the comparison is %r, not %r" % (tuple(s.COMPARE_KEYS), S4_COMPARE_KEYS))
        assert s.COVERAGE_WEIGHT == S4_COVERAGE_WEIGHT, (
            "the coverage weight is %r, not %r" % (s.COVERAGE_WEIGHT, S4_COVERAGE_WEIGHT))
        assert s.PROXIMITY_WEIGHT == S4_PROXIMITY_WEIGHT, (
            "the proximity weight is %r, not %r"
            % (s.PROXIMITY_WEIGHT, S4_PROXIMITY_WEIGHT))
        assert s.WEIGHT_TOTAL == S4_WEIGHT_TOTAL, (
            "the two weights add up to %r, not %r" % (s.WEIGHT_TOTAL, S4_WEIGHT_TOTAL))
        assert s.PROXIMITY_WINDOW == S4_PROXIMITY_WINDOW, (
            "the proximity window is %r positions, not %r"
            % (s.PROXIMITY_WINDOW, S4_PROXIMITY_WINDOW))
        assert s.LEVEL_BONUS_BP == S4_LEVEL_BONUS_BP, (
            "the level bonus is %r basis points, not %r"
            % (s.LEVEL_BONUS_BP, S4_LEVEL_BONUS_BP))
        assert s.NOISE_BP == S4_NOISE_BP, (
            "the noise bound is %r basis points, not %r" % (s.NOISE_BP, S4_NOISE_BP))

    def _s4_holder(library, chunks, wanted):
        """The first chunk of the index that holds every term of `wanted`."""
        for chunk in chunks:
            held = set(library.terms(chunk["text"]))
            if set(wanted) <= held:
                return chunk, held
        return None, None

    def _s4_signals(s, three, world):
        library = world.Corpus.build(7)
        index = three.Index.build(library)
        chunk, held = _s4_holder(library, index.chunks, ("payment", "due"))
        assert chunk is not None, (
            "no chunk of this corpus holds both `payment` and `due`, so coverage has "
            "nothing to be computed over")
        chunk_id = _s4_id(chunk)
        bonus = _s4_bonus(chunk)

        # the coverage is the share of the query's *distinct* terms the chunk holds
        query = "payment due zzzq payment"
        wanted = ("payment", "due", "zzzq")
        covered = tuple(term for term in wanted if term in held)
        assert len(covered) == 2, (
            "this corpus's `payment`/`due` chunk holds %d of %r, so the fixture is not "
            "the one it claims to be" % (len(covered), wanted))
        record = _s4_checked(_s4_one(s, index, chunk_id, query))
        signals = dict(record["signals"])
        assert signals["coverage"] == len(covered) * S4_WHOLE_BP // len(wanted), (
            "the coverage of %d of a query's %d distinct terms is %r, and a repeated term "
            "is being counted more than once" % (len(covered), len(wanted),
                                                 signals["coverage"]))
        assert 0 <= signals["proximity"] <= S4_WHOLE_BP, (
            "the proximity of %r is %r, not a share in basis points"
            % (chunk_id, signals["proximity"]))
        assert record["score"] == (signals["coverage"] * S4_COVERAGE_WEIGHT // S4_WEIGHT_TOTAL
                                   + signals["proximity"] * S4_PROXIMITY_WEIGHT
                                   // S4_WEIGHT_TOTAL + bonus), (
            "the score of %r does not carry the weights the contract fixes it at: %r"
            % (chunk_id, record))

        # a query with no terms at all covers nothing, and its score is the bonus alone
        empty = _s4_checked(_s4_one(s, index, chunk_id, "?!"))
        assert dict(empty["signals"]) == {"coverage": 0, "level-bonus": bonus,
                                          "proximity": 0}, (
            "a query with no analyzed terms did not answer zero coverage and zero "
            "proximity: %r" % (empty,))
        assert empty["score"] == bonus, (
            "a query with no terms scored %r, not the level bonus %r"
            % (empty["score"], bonus))

        # the level bonus is paid to the outermost level and to no other
        deeper = next((one for one in index.chunks if one["level"] != 1), None)
        assert deeper is not None, "this corpus has no clause below the outermost level"
        deep = _s4_checked(_s4_one(s, index, _s4_id(deeper), "?!"))
        assert dict(deep["signals"])["level-bonus"] == 0, (
            "a level %r clause was paid the level bonus: %r"
            % (deeper["level"], deep["signals"]))
        assert deep["score"] == 0, (
            "a level %r clause with no query terms scored %r, not zero"
            % (deeper["level"], deep["score"]))
        level_one = next((one for one in index.chunks if one["level"] == 1), None)
        assert level_one is not None, "this corpus has no outermost clause"
        top = _s4_checked(_s4_one(s, index, _s4_id(level_one), "?!"))
        assert dict(top["signals"])["level-bonus"] == S4_LEVEL_BONUS_BP, (
            "the outermost clause %r was not paid the level bonus: %r"
            % (_s4_id(level_one), top["signals"]))
        assert top["score"] == S4_LEVEL_BONUS_BP, (
            "the outermost clause scored %r, not the level bonus" % (top["score"],))

    def _s4_proximity(s, three, world):
        library = world.Corpus.build(7)
        index = three.Index.build(library)
        inside, outside = _s4_window(library, index.chunks, S4_PROXIMITY_WINDOW)
        assert inside is not None, (
            "no chunk of this corpus holds two distinct terms exactly %d positions apart, "
            "so the near side of the window cannot be pinned" % (S4_PROXIMITY_WINDOW,))
        assert outside is not None, (
            "no chunk of this corpus holds two distinct terms exactly %d positions apart, "
            "so the far side of the window cannot be pinned" % (S4_PROXIMITY_WINDOW + 1,))
        near_chunk, near_one, near_other = inside
        near = dict(_s4_checked(
            _s4_one(s, index, _s4_id(near_chunk), "%s %s" % (near_one, near_other)))["signals"])
        assert near["coverage"] == S4_WHOLE_BP, (
            "a query of two terms the chunk holds covered %r of it, not all of it"
            % (near["coverage"],))
        assert near["proximity"] == S4_WHOLE_BP, (
            "two distinct query terms %d positions apart scored a proximity of %r, so the "
            "window is compared strictly rather than `<=`: %r"
            % (S4_PROXIMITY_WINDOW, near["proximity"], near))
        far_chunk, far_one, far_other = outside
        far = dict(_s4_checked(
            _s4_one(s, index, _s4_id(far_chunk), "%s %s" % (far_one, far_other)))["signals"])
        assert far["coverage"] == S4_WHOLE_BP, (
            "a query of two terms the chunk holds covered %r of it, not all of it"
            % (far["coverage"],))
        assert far["proximity"] == 0, (
            "two distinct query terms %d positions apart scored a proximity of %r, so the "
            "window is wider than it says" % (S4_PROXIMITY_WINDOW + 1, far["proximity"]))

        # one term repeated inside the window is not a neighbour of itself
        repeat_chunk, repeat_term = _s4_repeat(library, index.chunks, S4_PROXIMITY_WINDOW)
        assert repeat_chunk is not None, (
            "no chunk of this corpus repeats one of its terms inside %d positions, so the "
            "'another distinct term' rule cannot be pinned" % (S4_PROXIMITY_WINDOW,))
        alone = dict(_s4_checked(
            _s4_one(s, index, _s4_id(repeat_chunk), repeat_term))["signals"])
        assert alone["coverage"] == S4_WHOLE_BP, (
            "the single query term %r covered %r of the chunk that holds it"
            % (repeat_term, alone["coverage"]))
        assert alone["proximity"] == 0, (
            "the single distinct query term %r scored a proximity of %r by sitting next to "
            "itself" % (repeat_term, alone["proximity"]))

    def _s4_order(s, three, world):
        library = world.Corpus.build(7)
        index = three.Index.build(library)
        big, small = _s4_pair(index.chunks, 1)
        tie = [{"chunk": big, "score": 0, "why": ()}, {"chunk": small, "score": 0, "why": ()}]
        kept = [hit["chunk"] for hit in s.rerank(index, "?!", tie, 5)]
        assert kept == [big, small], (
            "two hits that scored the same came back %r, so a tie is not keeping the input "
            "order (stage 3's, already broken by chunk id)" % (kept,))

        deeper = next((one for one in index.chunks if one["level"] != 1), None)
        assert deeper is not None, "this corpus has no clause below the outermost level"
        deep_id = _s4_id(deeper)
        ordered = [hit["chunk"] for hit in s.rerank(index, "?!", tie[:1] + [{"chunk": deep_id,
                                                                           "score": 0,
                                                                           "why": ()}], 5)]
        assert ordered == [big, deep_id], (
            "the higher-scoring hit did not come first: %r" % (ordered,))

        hits = index.fused("payment due", 5)
        assert len(hits) >= 3, (
            "the fused ranking of `payment due` holds %d hits, too few to pin a cut"
            % (len(hits),))
        ranked = s.rerank(index, "payment due", hits, 3)
        assert len(ranked) == 3, (
            "a limit of three answered %d hits" % (len(ranked),))
        assert {hit["chunk"] for hit in ranked} <= {hit["chunk"] for hit in hits}, (
            "the reranker answered a chunk the fusion never scored: %r" % (ranked,))
        assert s.rerank(index, "payment due", hits, 0) == (), (
            "a limit of zero answered something")
        assert len(s.rerank(index, "payment due", hits, 99)) == len(hits), (
            "a limit past the hits dropped one of them")
        assert s.rerank(index, "payment due", (), 5) == (), (
            "reranking no hits answered something")

        _refuses(ValueError, "a hit that is not a hit",
                 lambda: s.rerank(index, "payment due", ["nope"], 5), names=("nope",))
        _refuses(ValueError, "a hit for a chunk the index does not hold",
                 lambda: s.rerank(index, "payment due", [{"chunk": "zzz:9.9"}], 5),
                 names=("zzz:9.9",))
        _refuses(ValueError, "a limit that is a negative count",
                 lambda: s.rerank(index, "payment due", hits, -1), names=("-1",))
        _refuses(ValueError, "a limit that is not a whole number",
                 lambda: s.rerank(index, "payment due", hits, "3"), names=("3",))
        _refuses(ValueError, "a query that is not a string",
                 lambda: s.rerank(index, 7, hits, 3), names=("the text",))
        _refuses(ValueError, "an index that does not answer the customer's analyzer",
                 lambda: s.rerank(object(), "payment", (), 5))

    def _s4_ledger(s, three, world):
        library = world.Corpus.build(7)
        index = three.Index.build(library)
        hits = index.fused("payment due", 5)
        before = library.stats()
        s.rerank(index, "payment due", hits, 5)
        after = library.stats()
        assert after["analyses"] > before["analyses"], (
            "a rerank asked the customer's analyzer for nothing, so the coverage is not "
            "the customer's own analysis: %r" % (after,))
        assert after["embeds"] == before["embeds"], (
            "a rerank asked the customer's library to embed something, which a rerank "
            "never does: %r" % (after,))
        quiet = library.stats()["analyses"]
        _refuses(ValueError, "a rerank of a hit the index cannot place",
                 lambda: s.rerank(index, "payment due",
                                  [{"chunk": "zzz:9.9", "score": 0, "why": ()}], 5),
                 names=("zzz:9.9",))
        assert library.stats()["analyses"] == quiet, (
            "a refused rerank asked the customer's analyzer for something anyway: %r"
            % (library.stats(),))

    def _s4_after(s, three, index, questions, limit):
        """The check's own reading of `after`: the whole fusion, reranked, counted."""
        retrieved = []
        for question in questions:
            candidates = three.search(index, question["text"], len(index.chunks), "hybrid")
            ranked = s.rerank(index, question["text"], candidates, limit)
            retrieved.append(tuple(hit["chunk"] for hit in ranked))
        return _s4_count(retrieved, questions)

    def _s4_compare(s, three, world):
        library = world.Corpus.build(7)
        index = three.Index.build(library)
        questions = library.questions
        for limit in (3, 5):
            compared = s.compare(index, questions, limit)
            assert tuple(compared) == S4_COMPARE_KEYS, (
                "the comparison is %r, not %r" % (tuple(compared), S4_COMPARE_KEYS))
            assert tuple(compared["before"]) == three.MEASURE_KEYS, (
                "the comparison's `before` is %r, not a measurement"
                % (tuple(compared["before"]),))
            assert compared["before"] == three.measure(index, questions, limit, "hybrid"), (
                "the comparison's `before` is not stage 3's own hybrid measurement over the "
                "same questions and the same limit")
            assert tuple(compared["after"]) == three.MEASURE_KEYS, (
                "the comparison's `after` is %r, not a measurement"
                % (tuple(compared["after"]),))
            after = _s4_after(s, three, index, questions, limit)
            assert compared["after"] == after, (
                "the comparison's `after` is not the same counting over the whole fused "
                "ranking reranked down to the same limit: %r against %r"
                % (compared["after"], after))
            assert compared["delta_bp"] == after["hit_bp"] - compared["before"]["hit_bp"], (
                "the delta is not `after - before` of the two measurements")
            assert 0 <= compared["after"]["hit_bp"] <= S4_WHOLE_BP, (
                "the coverage %r is not a share in basis points"
                % (compared["after"]["hit_bp"],))
            expected = ("hurt" if compared["delta_bp"] < 0
                        else "within-noise" if compared["delta_bp"] < S4_NOISE_BP
                        else "earned")
            assert compared["verdict"] in S4_VOCABULARY, (
                "the verdict %r is not one of %r"
                % (compared["verdict"], S4_VOCABULARY))
            assert compared["verdict"] == expected, (
                "a delta of %r basis points read %r, not %r"
                % (compared["delta_bp"], compared["verdict"], expected))
            assert s.keep(index, questions, limit) == ("keep" if expected == "earned"
                                                        else "remove"), (
                "keep does not agree with the verdict %r" % (expected,))
        _refuses(ValueError, "a question that is not a question",
                 lambda: s.compare(index, ["nope"], 5), names=("nope",))
        _refuses(ValueError, "a question with no text",
                 lambda: s.compare(index, [{"qid": "q-x", "expected": ()}], 5),
                 names=("q-x",))
        _refuses(ValueError, "a question with no expected ids",
                 lambda: s.compare(index, [{"qid": "q-y", "text": "payment",
                                            "conversation": ()}], 5),
                 names=("q-y",))
        _refuses(ValueError, "a limit that is not a whole number",
                 lambda: s.compare(index, questions, "5"), names=("5",))
        _refuses(ValueError, "a comparison with no limit at all",
                 lambda: s.compare(index, questions, -1), names=("-1",))

    def _s4_boundary(s, three, world):
        library = world.Corpus.build(7)
        index = three.Index.build(library)
        query, front, promoted = _s4_flip(s, three, index, library)
        assert front != promoted, (
            "the fixture query does not move the front hit, so nothing can be measured")
        ghosts = tuple("ghost:%d.1" % (number,) for number in range(1, 101))

        def asked(qid, expected):
            return [{"qid": qid, "text": query, "expected": expected, "conversation": ()}]

        # a gain of exactly the noise bound earns its place
        earning = asked("b-earned", (promoted,) + ghosts[:49])
        earned = s.compare(index, earning, 1)
        assert earned["before"]["hit_bp"] == 0, (
            "the fusion already put the promoted id in front of the customer, so this "
            "fixture is not a gain at all: %r" % (earned["before"],))
        assert earned["after"]["hit_bp"] == S4_NOISE_BP, (
            "one expected id out of fifty answered %r basis points, not the bound %r"
            % (earned["after"]["hit_bp"], S4_NOISE_BP))
        assert earned["after"]["answered"] == 0, (
            "a question whose expected ids are almost all ghosts was counted as answered")
        assert earned["delta_bp"] == S4_NOISE_BP, (
            "a gain of exactly the bound read a delta of %r" % (earned["delta_bp"],))
        assert earned["verdict"] == "earned", (
            "a gain of exactly the noise bound read %r, so the bound is compared strictly"
            % (earned["verdict"],))
        assert s.keep(index, earning, 1) == "keep", (
            "keep did not answer \"keep\" for a gain that exactly earned its place")

        # the same one-id gain spread over twice the ids is inside the noise
        noisy = asked("b-noise", (promoted,) + ghosts[:99])
        noise = s.compare(index, noisy, 1)
        assert noise["delta_bp"] == S4_NOISE_BP // 2, (
            "a gain of one id in a hundred read a delta of %r" % (noise["delta_bp"],))
        assert noise["verdict"] == "within-noise", (
            "a gain of %r basis points read %r, so the noise bound is not the boundary it "
            "says it is" % (noise["delta_bp"], noise["verdict"]))
        assert s.keep(index, noisy, 1) == "remove", (
            "keep did not answer \"remove\" for a gain inside the noise")

        # a loss of the front hit hurts
        losing = asked("b-hurt", (front,) + ghosts[:49])
        lost = s.compare(index, losing, 1)
        assert lost["delta_bp"] == -S4_NOISE_BP, (
            "losing the front hit read a delta of %r, not its negation"
            % (lost["delta_bp"],))
        assert lost["verdict"] == "hurt", (
            "a loss read %r, not \"hurt\"" % (lost["verdict"],))
        assert s.keep(index, losing, 1) == "remove", (
            "keep answered \"keep\" for a loss")

        # a wash is noise, not a verdict on the reranker's side
        washing = asked("b-wash", (front, promoted) + ghosts[:48])
        wash = s.compare(index, washing, 1)
        assert wash["delta_bp"] == 0, (
            "one id gained and one lost read a delta of %r, not zero" % (wash["delta_bp"],))
        assert wash["verdict"] == "within-noise", (
            "a comparison with no gain at all read %r, so a loss is not the only thing "
            "that hurts" % (wash["verdict"],))

        # the missed questions come back sorted, whatever order they were asked in
        two = s.compare(index, asked("b-two", (promoted,) + ghosts[:24])
                        + asked("b-one", (promoted,) + ghosts[:24]), 1)
        assert two["after"]["missed"] == ("b-one", "b-two"), (
            "the missed questions came back %r, not sorted by qid"
            % (two["after"]["missed"],))
        assert two["delta_bp"] == 2 * S4_WHOLE_BP // 50, (
            "two ids out of fifty read a delta of %r" % (two["delta_bp"],))
        assert two["verdict"] == "earned", (
            "a gain of %r basis points read %r" % (two["delta_bp"], two["verdict"]))

    def _s4_workload(s, three, world):
        """One whole pass of the stage over fixtures built here, as one tuple."""
        library = world.Corpus.build(7)
        index = three.Index.build(library)
        question = library.questions[0]
        hits = index.fused(question["text"], 5)
        return (s.rerank(index, question["text"], hits, 3),
                s.compare(index, library.questions, 5),
                s.keep(index, library.questions, 5))

    def _s4_twice(s, three, world):
        one = _s4_workload(s, three, world)
        two = _s4_workload(s, three, world)
        assert one == two, (
            "two runs of one workload answered differently, so a run is not a function of "
            "its inputs")

    import stage_04 as s
    import stage_03 as three
    import corpus as world
    _s4_constants(s)
    _s4_signals(s, three, world)
    _s4_proximity(s, three, world)
    _s4_order(s, three, world)
    _s4_ledger(s, three, world)
    _s4_compare(s, three, world)
    _s4_boundary(s, three, world)
    _s4_twice(s, three, world)

# --- stage 5 -----------------------------------------------------------------------
def check_5():
    import os
    import re
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "agentic-retrieval-from-scratch"

    C5_KEYS = ("kind", "before", "after", "why")

    C5_KINDS = ("pronoun", "acronym", "elliptical", "decomposition", "none")

    C5_MIN_TERMS = 3

    C5_SUBSET_WORDS = 8

    C5_SEED = 7

    def _repo(start=None):
        for candidate_start in (os.environ.get("K1_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "course.py")) or \
                        os.path.isfile(os.path.join(candidate, COURSE, "corpus.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set K1_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked
        against the message: an exception of the right family raised for the wrong
        reason is not the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return refused
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _c5_question(qid, text, expected=(), conversation=()):
        """One `QUESTION_KEYS` record — the shape the stage's own input has."""
        return {"qid": qid, "text": text, "expected": tuple(expected),
                "conversation": tuple({"speaker": "reader", "text": turn}
                                      for turn in conversation)}

    def _c5_chunk(doc, clause, text, refs=(), level=2):
        """One `stage_01.CHUNK_KEYS` chunk, in the shape the course cites."""
        return {"doc": doc, "clause": clause, "level": level, "text": text,
                "refs": tuple(refs), "defines": ()}

    def _c5_words(text):
        """`text`'s whole words, as written, in order — the check's own tokenizer."""
        return re.findall("[0-9A-Za-z]+", text)

    def _c5_reorder(text, wanted, build):
        """`text` with every whole word whose lower case is in `wanted` rebuilt.

        The check's own answer, written with the regex engine rather than with the
        stage's scanner: answers the new text and the words it replaced.
        """
        hit = []

        def one(match):
            token = match.group(0)
            if token.lower() in wanted:
                hit.append(token)
                return build(token)
            return token

        return re.sub("[0-9A-Za-z]+", one, text), tuple(hit)

    def _c5_row(stage, kind, before, after, why):
        """One recorded fix, in the fields' own order."""
        return dict(zip(stage.REWRITE_KEYS, (kind, before, after, why)))

    def _c5_referent(stage, corpus, question):
        """The check's own reading of where a pronoun's referent comes from."""
        turns = question["conversation"]
        if not turns:
            return None
        runs = []
        run = []
        for token in corpus.terms(turns[-1]["text"]):
            if token in stage.REFERENT_STOP:
                if run:
                    runs.append(" ".join(run))
                    run = []
                continue
            run.append(token)
        if run:
            runs.append(" ".join(run))
        return runs[-1] if runs else None

    def _c5_fixes(stage, corpus, question):
        """The check's own answer to `rewrite`: the text and the rows it must record."""
        text = question["text"]
        rows = []
        referent = _c5_referent(stage, corpus, question)
        acronyms = {key.lower(): value.lower()
                    for key, value in corpus.glossary.items()}
        if referent is not None:
            before = text
            text, hit = _c5_reorder(text, set(stage.PRONOUNS), lambda token: referent)
            if hit:
                rows.append(_c5_row(stage, "pronoun", before, text,
                                    "%s -> %s" % (hit[0].lower(), referent)))
        before = text
        text, hit = _c5_reorder(text, set(acronyms), lambda token: "%s (%s)"
                                % (token, acronyms[token.lower()]))
        if hit:
            rows.append(_c5_row(stage, "acronym", before, text,
                                "%s -> %s" % (hit[0], acronyms[hit[0].lower()])))
        before = text
        content = [term for term in corpus.terms(question["text"])
                   if term not in stage.QUESTION_STOP]
        if len(content) < stage.MIN_INTERROGATIVE_TERMS and referent is not None:
            text = text + " " + referent
            rows.append(_c5_row(stage, "elliptical", before, text,
                                "referent -> %s" % (referent,)))
        return text, tuple(rows)

    def _c5_decompose_want(stage, corpus, question, chunks):
        """The check's own answer to `decompose`, over an id-keyed chunk map."""
        expected = question["expected"]
        if len(expected) < 2:
            return (question["text"],)
        first = chunks.get(expected[0])
        second = chunks.get(expected[1])
        if first is None or second is None:
            return (question["text"],)
        if expected[1].split(":", 1)[-1] not in first["refs"]:
            return (question["text"],)
        return (question["text"],
                " ".join(corpus.terms(second["text"])[:stage.SUBSET_WORDS]))

    def _c5_kinds(rows):
        """The kinds a run of rows recorded, in the order it recorded them."""
        return [row["kind"] for row in rows]

    def _c5_constants(s):
        assert tuple(s.REWRITE_KEYS) == C5_KEYS, (
            "one recorded fix carries %r, in that order, and the stage declares %r"
            % (C5_KEYS, tuple(s.REWRITE_KEYS)))
        assert tuple(s.REWRITE_KINDS) == C5_KINDS, (
            "the kinds a fix can have are %r, in the order they apply, and the stage "
            "declares %r" % (C5_KINDS, tuple(s.REWRITE_KINDS)))
        assert s.MIN_INTERROGATIVE_TERMS == C5_MIN_TERMS, (
            "a question stands alone from %d terms on, and the stage says %r"
            % (C5_MIN_TERMS, s.MIN_INTERROGATIVE_TERMS))
        assert s.SUBSET_WORDS == C5_SUBSET_WORDS, (
            "a second query keeps the first %d terms, and the stage says %r"
            % (C5_SUBSET_WORDS, s.SUBSET_WORDS))
        for name, words in (("PRONOUNS", s.PRONOUNS), ("REFERENT_STOP", s.REFERENT_STOP),
                            ("QUESTION_STOP", s.QUESTION_STOP)):
            assert isinstance(words, tuple) and words, (
                "%s is a non-empty tuple of words, and it is %r" % (name, words))
            assert len(set(words)) == len(words), (
                "%s holds a word twice, so one of the two lists it is read as is not the "
                "list it is: %r" % (name, words))
            for word in words:
                assert word == word.lower(), (
                    "%s is read against the analyzer's lower-case tokens, and %r is not "
                    "lower case" % (name, word))
        for word in ("it", "its", "we", "them"):
            assert word in s.PRONOUNS, (
                "%r is a pronoun the customer's own questions hide their subject behind, "
                "and PRONOUNS does not hold it: %r" % (word, s.PRONOUNS))
        for word in ("what", "which", "how"):
            assert word not in s.PRONOUNS, (
                "%r asks the question rather than pointing back at the conversation, so it "
                "is not a pronoun: %r" % (word, s.PRONOUNS))
        for word in ("the", "of", "them"):
            assert word in s.REFERENT_STOP, (
                "%r may not be part of a referent, and REFERENT_STOP does not hold it: %r"
                % (word, s.REFERENT_STOP))
        for word in ("the", "is", "how", "does"):
            assert word in s.QUESTION_STOP, (
                "%r is not a term a question is made of, and QUESTION_STOP does not hold "
                "it: %r" % (word, s.QUESTION_STOP))
        assert s.REWRITE_KINDS[-1] == "none", (
            "`none` is the last kind of the vocabulary, and the stage ends with %r"
            % (s.REWRITE_KINDS[-1],))

    def _c5_corpus(s, world):
        """Every one of the customer's own questions, against the check's own reading."""
        corpus = world.Corpus.build(C5_SEED)
        seen = {"pronoun": 0, "acronym": 0, "elliptical": 0, "bare": 0}
        for question in corpus.questions:
            text, rows = s.rewrite(corpus, question)
            want_text, want_rows = _c5_fixes(s, corpus, question)
            assert text == want_text, (
                "the rewritten text of %r is %r, and the rule the contract pins reads %r"
                % (question["qid"], text, want_text))
            assert tuple(rows) == want_rows, (
                "the fixes recorded for %r are %r, and the rule reads %r"
                % (question["qid"], tuple(rows), want_rows))
            assert s.ambiguous(corpus, question) == tuple(rows), (
                "`ambiguous` answers the rows `rewrite` applied, and for %r they are %r "
                "and %r" % (question["qid"], s.ambiguous(corpus, question), tuple(rows)))
            kinds = _c5_kinds(rows)
            for kind in kinds:
                assert kind in s.REWRITE_KINDS, (
                    "a fix of kind %r is not one of the kinds the vocabulary closes: %r"
                    % (kind, tuple(s.REWRITE_KINDS)))
                seen[kind] = seen.get(kind, 0) + 1
            assert kinds == sorted(kinds, key=s.REWRITE_KINDS.index), (
                "the fixes of %r are recorded in the order they apply, and they came back "
                "as %r" % (question["qid"], kinds))
            for row in rows:
                assert tuple(row) == C5_KEYS, (
                    "a recorded fix carries %r, in order, and one carries %r"
                    % (C5_KEYS, tuple(row)))
                assert isinstance(row["why"], str) and row["why"], (
                    "a recorded fix says why it was made, and %r does not" % (row["why"],))
            if not kinds:
                seen["bare"] = seen["bare"] + 1
        for kind in ("pronoun", "acronym", "elliptical"):
            assert seen[kind] > 0, (
                "the customer's own questions never need a %s fix, so the rule for it is "
                "unreachable: %r" % (kind, corpus.questions))
        assert seen["bare"] > 0, (
            "every question of the customer's own is rewritten, and an unambiguous question "
            "answers no rows at all: %r" % (seen,))

    def _c5_pronouns(s, world):
        corpus = world.Corpus.build(C5_SEED)
        turns = ("The licence and the amendment disagree about liability.",
                 "One of them removes the cap entirely.")
        question = _c5_question("x-close", "Is its cap still in force?",
                                conversation=turns)
        referent = _c5_referent(s, corpus, question)
        assert referent == "cap entirely", (
            "the referent is the last run of the last turn's analyzer tokens, and the "
            "check's own reading of the last turn is %r" % (referent,))
        text, rows = s.rewrite(corpus, question)
        assert _c5_kinds(rows) == ["pronoun"], (
            "a question with a pronoun and enough terms of its own records the pronoun fix "
            "and nothing else, and it recorded %r" % (_c5_kinds(rows),))
        assert rows[0]["after"] == "Is cap entirely cap still in force?", (
            "every whole-word occurrence of the pronoun is replaced by the referent, and "
            "the text came back as %r" % (rows[0]["after"],))
        assert rows[0]["before"] == question["text"], (
            "the first fix's `before` is the question as it arrived: %r" % (rows[0]["before"],))
        assert rows[0]["why"] == "its -> cap entirely", (
            "the row says which pronoun it replaced and with what, and it says %r"
            % (rows[0]["why"],))
        assert text == rows[0]["after"], (
            "the text `rewrite` answers is the last row's `after`: %r and %r"
            % (text, rows[0]["after"]))
        shouted = _c5_question("x-shouted", "Is ITS cap still in force?",
                               conversation=turns)
        text, rows = s.rewrite(corpus, shouted)
        assert text == "Is cap entirely cap still in force?", (
            "a pronoun is matched whatever its case, and the text came back as %r" % (text,))
        assert rows[0]["why"] == "its -> cap entirely", (
            "the row names the pronoun in its lower-case form, and it names %r"
            % (rows[0]["why"],))
        trap = _c5_question("x-itself", "Does the licence renew itself for a longer term?",
                            conversation=turns)
        assert s.ambiguous(corpus, trap) == (), (
            "`itself` is not `its`, so a whole-word match rewrites nothing, and the stage "
            "rewrote %r" % (s.ambiguous(corpus, trap),))
        lonely = _c5_question("x-lonely", "Is its cap still in force?")
        assert s.ambiguous(corpus, lonely) == (), (
            "a question with no conversation has no referent, so no pronoun is rewritten, "
            "and the stage rewrote %r" % (s.ambiguous(corpus, lonely),))
        mute = _c5_question("x-mute", "Is its cap still in force?",
                            conversation=("It is one of them.",))
        assert _c5_referent(s, corpus, mute) is None, (
            "a last turn whose every token is a stop word names nothing")
        assert s.ambiguous(corpus, mute) == (), (
            "a turn that names nothing is not a referent, and the stage rewrote %r"
            % (s.ambiguous(corpus, mute),))
        other = _c5_question("x-other", "Is its cap still in force?",
                             conversation=("One of them removes the cap entirely.",))
        assert s.rewrite(corpus, other)[0] == "Is cap entirely cap still in force?", (
            "the referent comes from the last turn, and with one turn that is the first: %r"
            % (s.rewrite(corpus, other)[0],))
        first_only = _c5_question("x-first", "Is its cap still in force?",
                                  conversation=("The licence disagrees about liability.",))
        assert s.rewrite(corpus, first_only)[0] == \
            "Is liability cap still in force?", (
            "the first turn's last run is not the referent once a later turn exists: %r"
            % (s.rewrite(corpus, first_only)[0],))

    def _c5_acronyms(s, world):
        corpus = world.Corpus.build(C5_SEED)
        glossary = {key.lower(): value.lower()
                    for key, value in corpus.glossary.items()}
        carriers = [question for question in corpus.questions
                    if [word for word in _c5_words(question["text"])
                        if word.lower() in glossary]]
        assert len(carriers) >= 3, (
            "the customer's own questions carry an acronym of the customer's glossary, and "
            "only %r do, so the acronym fix is nearly unreachable: %r"
            % ([question["qid"] for question in carriers], corpus.glossary))
        for question in carriers:
            text, rows = s.rewrite(corpus, question)
            assert "acronym" in _c5_kinds(rows), (
                "the question %r carries an acronym the glossary holds, so the acronym fix "
                "applies, and the stage recorded %r" % (question["qid"], _c5_kinds(rows)))
            for word in sorted(set(_c5_words(question["text"]))):
                if word.lower() not in glossary:
                    continue
                expansion = glossary[word.lower()]
                assert "%s (%s)" % (word, expansion) in text, (
                    "the acronym %r is kept, whatever its case, and the expansion the "
                    "library holds follows it in parentheses: %r" % (word, text))
        first = carriers[0]
        text, rows = s.rewrite(corpus, first)
        word = [one for one in _c5_words(first["text"]) if one.lower() in glossary][0]
        expansion = glossary[word.lower()]
        expanded = "%s (%s)" % (word, expansion)
        assert expanded in text, (
            "the acronym %r is expanded and kept as %r, and the text %r of %r does not hold "
            "it" % (word, expanded, text, first["qid"]))
        row = [one for one in rows if one["kind"] == "acronym"][0]
        assert row["after"] == row["before"].replace(word, expanded), (
            "the recorded fix's text is the one before it with %r put in the acronym's "
            "place, and it came back as %r" % (expanded, row["after"]))
        assert row["why"] == "%s -> %s" % (word, expansion), (
            "the row names the acronym as written and the expansion the library holds, and "
            "it names %r" % (row["why"],))
        lower = _c5_question("x-lower", "Does the sla still bind the parties for a year?")
        text, rows = s.rewrite(corpus, lower)
        assert text == ("Does the sla (service level agreement) still bind the parties for "
                        "a year?"), (
            "an acronym written in lower case is matched and expanded where it stands, and "
            "the text came back as %r" % (text,))
        assert _c5_kinds(rows) == ["acronym"], (
            "the customer's glossary holds `sla`, so the acronym fix applies, and the stage "
            "recorded %r" % (_c5_kinds(rows),))
        assert rows[0]["why"] == "sla -> service level agreement", (
            "the row names the acronym as written and the expansion the glossary holds, and "
            "it names %r" % (rows[0]["why"],))
        trap = _c5_question("x-msas", "Is the MSAS fee schedule still binding for a year?")
        assert s.ambiguous(corpus, trap) == (), (
            "`MSAS` merely contains `MSA`, and a whole-word match expands nothing: %r"
            % (s.ambiguous(corpus, trap),))

    def _c5_elliptical(s, world):
        corpus = world.Corpus.build(C5_SEED)
        turns = ("The licence and the amendment disagree about liability.",
                 "One of them removes the cap entirely.")
        short = _c5_question("x-short", "Is its cap gone?", conversation=turns)
        text, rows = s.rewrite(corpus, short)
        assert _c5_kinds(rows) == ["pronoun", "elliptical"], (
            "a question one term short of standing alone appends its referent, and the "
            "stage recorded %r" % (_c5_kinds(rows),))
        assert rows[1]["before"] == rows[0]["after"], (
            "the elliptical fix applies to the text the pronoun fix produced: %r and %r"
            % (rows[1]["before"], rows[0]["after"]))
        assert rows[1]["after"] == rows[0]["after"] + " cap entirely", (
            "the referent is appended, separated by exactly one space, and the text is %r"
            % (rows[1]["after"],))
        assert rows[1]["why"] == "referent -> cap entirely", (
            "the appended row names the referent it appended, and it names %r"
            % (rows[1]["why"],))
        assert text == rows[1]["after"], (
            "the text `rewrite` answers is the appended row's `after`: %r" % (text,))
        exact = _c5_question("x-enough", "Is its cap still in force?",
                             conversation=turns)
        assert _c5_kinds(s.ambiguous(corpus, exact)) == ["pronoun"], (
            "exactly the minimum number of terms stands alone, so no referent is appended, "
            "and the stage recorded %r" % (_c5_kinds(s.ambiguous(corpus, exact)),))
        alone = _c5_question("x-alone", "Is its cap gone?")
        assert s.ambiguous(corpus, alone) == (), (
            "a question with no conversation has nothing to lean on, so nothing is "
            "appended: %r" % (s.ambiguous(corpus, alone),))
        mute = _c5_question("x-mute2", "Is it gone?", conversation=("It is one of them.",))
        assert s.ambiguous(corpus, mute) == (), (
            "an elliptical question whose last turn names nothing appends nothing: %r"
            % (s.ambiguous(corpus, mute),))

    def _c5_order(s, world):
        corpus = world.Corpus.build(C5_SEED)
        question = _c5_question("x-chain", "Is its SLA gone?", conversation=(
            "The licence and the amendment both mention a service level.",
            "One of them removes the cap entirely."))
        text, rows = s.rewrite(corpus, question)
        assert _c5_kinds(rows) == ["pronoun", "acronym", "elliptical"], (
            "the three fixes apply in REWRITE_KINDS order, and this question's came back as "
            "%r" % (_c5_kinds(rows),))
        assert rows[0]["before"] == "Is its SLA gone?", (
            "the first fix's `before` is the question as it arrived, and it is %r"
            % (rows[0]["before"],))
        for before, after in zip(rows, rows[1:]):
            assert after["before"] == before["after"], (
                "each fix applies to the text the fixes before it produced, and %r is not "
                "the previous row's %r" % (after["before"], before["after"]))
        assert text == rows[-1]["after"], (
            "the text `rewrite` answers is the last row's `after`: %r and %r"
            % (text, rows[-1]["after"]))
        assert s.ambiguous(corpus, question) == tuple(rows), (
            "`ambiguous` answers the same rows `rewrite` applied: %r and %r"
            % (s.ambiguous(corpus, question), tuple(rows)))

    def _c5_decompose(s, world, s1):
        corpus = world.Corpus.build(C5_SEED)
        every = {}
        for document in corpus.documents:
            for chunk in s1.chunk(document)[0]:
                every[s1.chunk_id(chunk)] = chunk
        two_hop = []
        for question in corpus.questions:
            got = s.decompose(corpus, question, tuple(every.values()))
            want = _c5_decompose_want(s, corpus, question, every)
            assert got == want, (
                "the queries %r needs are %r, and the rule reads %r"
                % (question["qid"], got, want))
            assert 1 <= len(got) <= 2, (
                "a question needs one query or two, and %r needs %r"
                % (question["qid"], got))
            if len(got) == 2:
                two_hop.append(question["qid"])
            assert len(got) == 1 or got[0] == question["text"], (
                "the first query is the question's own text: %r" % (got[0],))
            for query in got:
                assert isinstance(query, str) and query, (
                    "a query is a non-empty string, and one is %r" % (query,))
        assert two_hop, (
            "no question of the customer's own is two hops, so the second query is "
            "unreachable: %r" % (corpus.questions,))
        chunks = (_c5_chunk("sow-1", "2.1", "Each deliverable is accepted or rejected "
                            "within ten business days, see 4.2.", ("4.2",)),
                  _c5_chunk("sow-1", "4.2", "A rejected deliverable is corrected once at "
                            "no charge."))
        two = _c5_question("x-two", "How long do we have to accept it?",
                           ("sow-1:2.1", "sow-1:4.2"))
        assert s.decompose(corpus, two, chunks) == (
            "How long do we have to accept it?",
            "a rejected deliverable is corrected once at no"), (
            "a two-hop question is its own text, then the referenced clause cut to its "
            "first %d terms: %r" % (C5_SUBSET_WORDS, s.decompose(corpus, two, chunks)))
        one = _c5_question("x-one", two["text"], ("sow-1:2.1",))
        assert s.decompose(corpus, one, chunks) == (two["text"],), (
            "a single-hop question needs one query, and the stage answered %r"
            % (s.decompose(corpus, one, chunks),))
        apart = _c5_question("x-apart", two["text"], ("sow-1:4.2", "sow-1:2.1"))
        assert s.decompose(corpus, apart, chunks) == (two["text"],), (
            "a reference that runs the other way is not a hop, and the stage answered %r"
            % (s.decompose(corpus, apart, chunks),))
        missing = _c5_question("x-missing", two["text"], ("sow-1:2.1", "sow-1:9.9"))
        assert s.decompose(corpus, missing, chunks) == (two["text"],), (
            "an expected id the chunk list does not hold is not a hop, and the stage "
            "answered %r" % (s.decompose(corpus, missing, chunks),))
        unknown = _c5_question("x-unknown", two["text"], ("sow-1:9.9", "sow-1:4.2"))
        assert s.decompose(corpus, unknown, chunks) == (two["text"],), (
            "a first hop the chunk list does not hold cannot point at anything, and the "
            "stage answered %r" % (s.decompose(corpus, unknown, chunks),))
        three = _c5_question("x-three", two["text"],
                             ("sow-1:2.1", "sow-1:4.2", "sow-1:1.1"))
        assert s.decompose(corpus, three, chunks) == s.decompose(corpus, two, chunks), (
            "the first two expected ids are the hops, and a third adds nothing: %r"
            % (s.decompose(corpus, three, chunks),))
        eight = "alpha beta gamma delta epsilon zeta eta theta"
        exact = (_c5_chunk("book", "1.1", "see 1.2", ("1.2",)),
                 _c5_chunk("book", "1.2", eight))
        longer = (_c5_chunk("book", "1.1", "see 1.2", ("1.2",)),
                  _c5_chunk("book", "1.2", eight + " iota"))
        question = _c5_question("x-cut", "What does the clause say?",
                                ("book:1.1", "book:1.2"))
        assert s.decompose(corpus, question, exact) == ("What does the clause say?", eight), (
            "exactly %d terms is not a cut, and the second query came back as %r"
            % (C5_SUBSET_WORDS, s.decompose(corpus, question, exact)[1]))
        assert s.decompose(corpus, question, longer)[1] == eight, (
            "one term past the cut drops the last one, and the second query came back as "
            "%r" % (s.decompose(corpus, question, longer)[1],))

    def _c5_refusals(s, world):
        corpus = world.Corpus.build(C5_SEED)
        question = _c5_question("x-ref", "Is its cap still in force?")
        chunks = (_c5_chunk("book", "1.1", "see 1.2", ("1.2",)),
                  _c5_chunk("book", "1.2", "beta gamma"))
        before = corpus.stats()
        _refuses(world.CorpusError, "a corpus that is a string",
                 lambda: s.ambiguous("corpus", question), names=("str",))
        _refuses(world.CorpusError, "a corpus that is a whole number",
                 lambda: s.rewrite(7, question), names=("int",))
        _refuses(world.CorpusError, "a question that is a string",
                 lambda: s.ambiguous(corpus, "question"), names=("str",))
        _refuses(world.CorpusError, "a question that is only an id",
                 lambda: s.ambiguous(corpus, {"qid": "x"}), names=("text",))
        _refuses(world.CorpusError, "a question with no id",
                 lambda: s.rewrite(corpus, {"text": "x", "expected": (),
                                            "conversation": ()}), names=("qid",))
        _refuses(world.CorpusError, "chunks that are a string",
                 lambda: s.decompose(corpus, question, "chunks"),
                 names=("chunks", "tuple"))
        _refuses(world.CorpusError, "a chunk that is a string",
                 lambda: s.decompose(corpus, question, ("chunk",)), names=("str",))
        _refuses(world.CorpusError, "a chunk the chunker did not build",
                 lambda: s.decompose(corpus, question, ({"clause": "1."},)), names=("doc",))
        _refuses(world.CorpusError, "a question with no expected ids",
                 lambda: s.decompose(corpus, {"qid": "x", "text": "x"}, chunks),
                 names=("expected",))
        assert corpus.stats() == before, (
            "a refused call asked the customer's library anyway: %r" % (corpus.stats(),))

    def _c5_ledger(s, world):
        corpus = world.Corpus.build(C5_SEED)
        turns = ("The licence and the amendment disagree about liability.",
                 "One of them removes the cap entirely.")
        with_turns = _c5_question("x-ledger", "Is its cap still in force?",
                                  conversation=turns)
        without = _c5_question("x-bare", "Is the cap still in force?")
        before = corpus.stats()
        s.rewrite(corpus, with_turns)
        after = corpus.stats()
        assert after["analyses"] - before["analyses"] == 2, (
            "the customer's analyzer is asked once for the question and once for its last "
            "turn, and the library counted %d analyses"
            % (after["analyses"] - before["analyses"],))
        before = corpus.stats()
        s.rewrite(corpus, without)
        after = corpus.stats()
        assert after["analyses"] - before["analyses"] == 1, (
            "a question with no conversation is analyzed once, and the library counted %d "
            "analyses" % (after["analyses"] - before["analyses"],))
        assert (after["idfs"], after["embeds"], after["lookups"]) == (0, 0, 0), (
            "this stage embeds nothing, prices nothing and looks nothing up, and the "
            "customer's library counted %r" % (after,))
        assert after["clauses"] > 0 and after["documents"] > 0, (
            "the customer's library is still the library it was built as: %r" % (after,))

    def _c5_workload(s, world, s1):
        """One whole pass of the stage over the customer's questions, as one tuple."""
        corpus = world.Corpus.build(C5_SEED)
        chunks = ()
        for document in corpus.documents:
            chunks = chunks + tuple(s1.chunk(document)[0])
        answers = []
        for question in corpus.questions:
            answers.append(s.ambiguous(corpus, question))
            answers.append(s.rewrite(corpus, question))
            answers.append(s.decompose(corpus, question, chunks))
        return tuple(answers)

    def _c5_twice(s, world, s1):
        one = _c5_workload(s, world, s1)
        two = _c5_workload(s, world, s1)
        assert one == two, (
            "two runs of one workload answered differently, so a run is not a function of "
            "its inputs")

    import corpus as world
    import stage_01 as s1
    import stage_05 as s
    _c5_constants(s)
    _c5_corpus(s, world)
    _c5_pronouns(s, world)
    _c5_acronyms(s, world)
    _c5_elliptical(s, world)
    _c5_order(s, world)
    _c5_decompose(s, world, s1)
    _c5_refusals(s, world)
    _c5_ledger(s, world)
    _c5_twice(s, world, s1)

# --- stage 6 -----------------------------------------------------------------------
def check_6():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "agentic-retrieval-from-scratch"

    C6_KEYS = ("chunk", "verdict", "reason", "against")

    C6_VERDICTS = ("supported", "conflicting", "stale", "off-topic", "unresolvable")

    C6_ORDER = ("stale", "unresolvable", "conflicting", "off-topic", "supported")

    C6_DANGLING = (("dpa-1:2.3", "9.9"),)

    C6_STATS = {"documents": 8, "clauses": 107}

    def _repo(start=None):
        for candidate_start in (os.environ.get("K1_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                here = os.path.join(candidate, COURSE)
                if (os.path.isfile(os.path.join(here, "course.py"))
                        or os.path.isfile(os.path.join(here, "corpus.py"))):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set K1_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked
        against the message: an exception of the right family raised for the wrong
        reason is not the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return refused
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _s6_chunk(index, chunk_id):
        """The chunk record `chunk_id` names in the index, or the fixture is broken."""
        chunk = index.of(chunk_id)
        assert chunk is not None, (
            "the fixture needs the chunk %r, and the index built from the corpus does not "
            "hold it" % (chunk_id,))
        return chunk

    def _s6_shape(rows):
        """Every row is a `CRITIQUE_KEYS` record whose verdict is in the vocabulary."""
        assert isinstance(rows, tuple), (
            "the critique answers a %s, and a collection this course returns is a tuple"
            % (type(rows).__name__,))
        for row in rows:
            assert tuple(row) == C6_KEYS, (
                "a critique row's fields are %r, not the record's own %r"
                % (tuple(row), C6_KEYS))
            assert row["verdict"] in C6_VERDICTS, (
                "a critique row's verdict is %r, which is not one of %r"
                % (row["verdict"], C6_VERDICTS))
        return rows

    def _s6_dangling(stage01, corpus):
        """Every (chunk id, ref) whose ref names a clause its own document never held."""
        found = []
        for document in corpus.documents:
            chunks, _problems = stage01.chunk(document)
            held = corpus.clause_index(document["doc"])
            for chunk in chunks:
                for ref in chunk["refs"]:
                    if ref not in held:
                        found.append((stage01.chunk_id(chunk), ref))
        return tuple(found)

    def _s6_constants(s, world):
        assert tuple(s.CRITIQUE_KEYS) == C6_KEYS, (
            "CRITIQUE_KEYS is %r, not the row's fields in their own order %r"
            % (tuple(s.CRITIQUE_KEYS), C6_KEYS))
        assert tuple(s.CRITIQUE_VERDICTS) == C6_VERDICTS, (
            "CRITIQUE_VERDICTS is %r, not the closed vocabulary %r"
            % (tuple(s.CRITIQUE_VERDICTS), C6_VERDICTS))
        assert tuple(s.VERDICT_ORDER) == C6_ORDER, (
            "VERDICT_ORDER is %r, not the priority %r — a chunk true of two verdicts must "
            "be named by the first" % (tuple(s.VERDICT_ORDER), C6_ORDER))
        assert set(s.CRITIQUE_VERDICTS) == set(s.VERDICT_ORDER), (
            "the vocabulary %r and the order %r do not name the same verdicts"
            % (s.CRITIQUE_VERDICTS, s.VERDICT_ORDER))

    def _s6_catalog(stage01, corpus, index):
        """The fixtures below are real: the corpus and stage 1 hold what they claim."""
        stats = corpus.stats()
        assert stats["documents"] == C6_STATS["documents"], (
            "the corpus recounts %r documents, not the fixture's %r"
            % (stats["documents"], C6_STATS["documents"]))
        assert stats["clauses"] == C6_STATS["clauses"], (
            "the corpus recounts %r clauses, not the fixture's %r"
            % (stats["clauses"], C6_STATS["clauses"]))
        found = _s6_dangling(stage01, corpus)
        assert found == C6_DANGLING, (
            "stage 1 reads the corpus's dangling references as %r, not %r"
            % (found, C6_DANGLING))
        superseded = [d["doc"] for d in corpus.documents if d["superseded_by"] is not None]
        assert superseded == ["lic-2"], (
            "the corpus's superseded documents are %r, and this check critiques the chunk "
            "of the one it has" % (superseded,))
        subjects = corpus.subjects()
        assert subjects["msa-3:3.2"] == subjects["sow-1:4.1"], (
            "the payment pair does not share a subject, so it is no conflict fixture: "
            "%r vs %r" % (subjects["msa-3:3.2"], subjects["sow-1:4.1"]))
        assert subjects["lic-2:6.1"] == subjects["amd-3:3.1"], (
            "the liability pair does not share a subject: %r vs %r"
            % (subjects["lic-2:6.1"], subjects["amd-3:3.1"]))
        assert subjects["dpa-1:2.3"] == subjects["msa-3:2.1"], (
            "the dangling chunk and its would-be partner do not share a subject: %r vs %r"
            % (subjects["dpa-1:2.3"], subjects["msa-3:2.1"]))
        for chunk_id in ("lic-2:6.1", "amd-3:3.1", "msa-3:3.2", "sow-1:4.1", "dpa-1:2.3",
                         "msa-3:2.1", "sec-1:2.1", "res-1:1.1", "amd-3:4.1"):
            _s6_chunk(index, chunk_id)

    def _s6_stale(s, index, corpus):
        chunk = _s6_chunk(index, "lic-2:6.1")
        rows = _s6_shape(s.critique((chunk,), "liability", corpus))
        assert len(rows) == 1, (
            "one chunk in, %d rows out: the critique is one row per input chunk"
            % (len(rows),))
        assert rows[0]["chunk"] == "lic-2:6.1", (
            "the row names the chunk %r, not the chunk that came in" % (rows[0]["chunk"],))
        assert rows[0]["verdict"] == "stale", (
            "a chunk of the superseded lic-2 is %r, and supersession is a fact about its "
            "document" % (rows[0]["verdict"],))
        assert rows[0]["reason"] == "superseded by amd-3", (
            "the reason is %r, not the superseding document's own id"
            % (rows[0]["reason"],))
        assert rows[0]["against"] == "amd-3", (
            "the row is against %r, and a supersession is against the document that "
            "superseded it rather than against one of its chunks" % (rows[0]["against"],))
        again = _s6_shape(s.critique((chunk,), "payment", corpus))
        assert again[0]["verdict"] == "stale", (
            "a superseded chunk whose text shares no query term is %r, and stale is the "
            "first thing true of it" % (again[0]["verdict"],))
        assert again[0]["reason"] == "superseded by amd-3", (
            "the priority changed the reason as well: %r" % (again[0]["reason"],))
        live = _s6_chunk(index, "amd-3:3.1")
        row = s.critique((live,), "liability", corpus)[0]
        assert row["verdict"] == "supported", (
            "the amendment that superseded the licence is itself %r for the query it "
            "answers" % (row["verdict"],))
        assert row["against"] is None, (
            "a supported chunk was judged against %r, and nothing is true of it"
            % (row["against"],))

    def _s6_conflict(s, index, corpus):
        paid = _s6_chunk(index, "msa-3:3.2")
        invoiced = _s6_chunk(index, "sow-1:4.1")
        rows = _s6_shape(s.critique((paid, invoiced), "payment", corpus))
        assert [row["chunk"] for row in rows] == ["msa-3:3.2", "sow-1:4.1"], (
            "the rows came back as %r, and the critique answers in input order"
            % ([row["chunk"] for row in rows],))
        assert rows[0]["verdict"] == "conflicting", (
            "two chunks that share the payment subject and disagree are %r, and the stage "
            "exists to name that" % (rows[0]["verdict"],))
        assert rows[0]["against"] == "sow-1:4.1", (
            "the conflict is against %r, not the other chunk that came back with it"
            % (rows[0]["against"],))
        assert rows[0]["reason"] == "contradicts sow-1:4.1", (
            "the conflict's reason is %r, not the offender's id" % (rows[0]["reason"],))
        assert rows[1]["verdict"] == "conflicting", (
            "the disagreement is not symmetric: the second chunk is %r"
            % (rows[1]["verdict"],))
        assert rows[1]["against"] == "msa-3:3.2", (
            "the second chunk is against %r, not the first" % (rows[1]["against"],))
        assert "payment" not in corpus.terms(invoiced["text"]), (
            "the fixture relies on sow-1:4.1 carrying no `payment` term, so that the "
            "conflict, and not `off-topic`, is what decides it")
        same = _s6_shape(s.critique((paid, paid), "payment", corpus))
        assert [row["verdict"] for row in same] == ["supported", "supported"], (
            "the same chunk handed in twice answers %r, and an equal text is a repetition "
            "rather than a disagreement" % ([row["verdict"] for row in same],))
        other = _s6_chunk(index, "msa-3:3.1")
        solo = _s6_shape(s.critique((paid, other), "payment", corpus))
        assert solo[0]["verdict"] == "supported", (
            "a chunk is %r though no chunk of the input shares its subject, so the conflict "
            "is being read from the document rather than from the subject"
            % (solo[0]["verdict"],))
        assert solo[1]["verdict"] == "off-topic", (
            "msa-3:3.1 shares no subject with the payment chunk and carries no query term, "
            "so it is %r" % (solo[1]["verdict"],))

    def _s6_unresolvable(s, index, corpus):
        dangling = _s6_chunk(index, "dpa-1:2.3")
        rows = _s6_shape(s.critique((dangling,), "sub-processors", corpus))
        assert rows[0]["verdict"] == "unresolvable", (
            "a chunk naming 9.9, which its own document never held, is %r"
            % (rows[0]["verdict"],))
        assert rows[0]["against"] == "9.9", (
            "the row is against %r, not the clause the chunk's own text names"
            % (rows[0]["against"],))
        assert rows[0]["reason"] == "dangling ref 9.9", (
            "the reason is %r, not the missing clause" % (rows[0]["reason"],))
        partner = _s6_chunk(index, "msa-3:2.1")
        both = _s6_shape(s.critique((dangling, partner), "sub-processors", corpus))
        assert both[0]["verdict"] == "unresolvable", (
            "a chunk that is both dangling and would conflict is %r, and unresolvable "
            "comes first" % (both[0]["verdict"],))
        assert both[1]["verdict"] == "conflicting", (
            "the chunk that shares a subject with a dangling chunk is %r"
            % (both[1]["verdict"],))
        assert both[1]["against"] == "dpa-1:2.3", (
            "it is against %r, not the chunk that is dangling" % (both[1]["against"],))

    def _s6_vocabulary(s, index, corpus):
        lic = _s6_chunk(index, "lic-2:6.1")
        paid = _s6_chunk(index, "msa-3:3.2")
        security = _s6_chunk(index, "sec-1:2.1")
        res = _s6_chunk(index, "res-1:1.1")
        rows = _s6_shape(s.critique((lic, paid, security), "payment liability", corpus))
        assert [row["verdict"] for row in rows] == ["stale", "supported", "off-topic"], (
            "the three chunks answer %r, and the order decides each of them"
            % ([row["verdict"] for row in rows],))
        assert rows[1]["reason"] == "1 query terms present", (
            "a chunk carrying one of the query's two terms says %r"
            % (rows[1]["reason"],))
        assert rows[1]["against"] is None, (
            "a supported chunk is against %r" % (rows[1]["against"],))
        assert rows[2]["reason"] == "no query term: payment", (
            "the first absent term in the query's own order is `payment`, and the reason "
            "says %r" % (rows[2]["reason"],))
        assert rows[2]["against"] is None, (
            "an off-topic chunk is against %r, not a corpus id" % (rows[2]["against"],))
        two = s.critique((paid,), "invoice payment", corpus)[0]
        assert two["reason"] == "2 query terms present", (
            "a chunk carrying both query terms says %r" % (two["reason"],))
        repeated = s.critique((paid,), "payment payment", corpus)[0]
        assert repeated["reason"] == "1 query terms present", (
            "the query's terms are distinct, so a word said twice is one term, and the "
            "reason says %r" % (repeated["reason"],))
        none = _s6_shape(s.critique((paid, security), "", corpus))
        assert [row["verdict"] for row in none] == ["supported", "supported"], (
            "a query with no terms at all leaves every chunk %r"
            % ([row["verdict"] for row in none],))
        assert none[0]["reason"] == "0 query terms present", (
            "a query with no terms says %r" % (none[0]["reason"],))
        assert s.critique((), "payment", corpus) == (), (
            "a critique of no chunks is not the empty answer")
        forward = _s6_shape(s.critique((security, paid), "payment", corpus))
        assert [row["chunk"] for row in forward] == ["sec-1:2.1", "msa-3:3.2"], (
            "the rows came back %r, and they are in input order rather than sorted"
            % ([row["chunk"] for row in forward],))

    def _s6_survivors(s, index, corpus):
        first = _s6_chunk(index, "amd-3:3.1")
        second = _s6_chunk(index, "amd-3:4.1")
        rows = _s6_shape(s.critique((first, second), "licence", corpus))
        assert [row["verdict"] for row in rows] == ["supported", "supported"], (
            "two live chunks carrying the query's term answer %r"
            % ([row["verdict"] for row in rows],))
        assert s.survivors(rows) == ("amd-3:3.1", "amd-3:4.1"), (
            "the survivors are %r, and they keep the rows' own order"
            % (s.survivors(rows),))
        swapped = s.critique((second, first), "licence", corpus)
        assert s.survivors(swapped) == ("amd-3:4.1", "amd-3:3.1"), (
            "the survivors are %r, so they were sorted rather than left in the rows' order"
            % (s.survivors(swapped),))
        lic = _s6_chunk(index, "lic-2:6.1")
        paid = _s6_chunk(index, "msa-3:3.2")
        dangling = _s6_chunk(index, "dpa-1:2.3")
        res = _s6_chunk(index, "res-1:1.1")
        mixed = _s6_shape(s.critique((lic, paid, dangling, res), "payment liability",
                                     corpus))
        assert [row["verdict"] for row in mixed] == ["stale", "supported", "unresolvable",
                                                     "off-topic"], (
            "the four chunks answer %r" % ([row["verdict"] for row in mixed],))
        assert s.survivors(mixed) == ("msa-3:3.2",), (
            "survivors keeps only the supported rows in their own order, and answered %r"
            % (s.survivors(mixed),))
        report = s.by_verdict(mixed)
        assert tuple(report) == C6_VERDICTS, (
            "by_verdict's keys are %r, not the vocabulary in its own order %r"
            % (tuple(report), C6_VERDICTS))
        for verdict in C6_VERDICTS:
            assert isinstance(report[verdict], tuple), (
                "by_verdict's %r holds %r, and every verdict holds a tuple of ids"
                % (verdict, report[verdict]))
        assert report["supported"] == ("msa-3:3.2",), (
            "by_verdict puts %r under supported" % (report["supported"],))
        assert report["stale"] == ("lic-2:6.1",), (
            "by_verdict puts %r under stale" % (report["stale"],))
        assert report["unresolvable"] == ("dpa-1:2.3",), (
            "by_verdict puts %r under unresolvable" % (report["unresolvable"],))
        assert report["off-topic"] == ("res-1:1.1",), (
            "by_verdict puts %r under off-topic" % (report["off-topic"],))
        assert report["conflicting"] == (), (
            "a verdict no row carries is present and empty, and by_verdict holds %r"
            % (report["conflicting"],))
        security = _s6_chunk(index, "sec-1:2.1")
        pair = _s6_shape(s.critique((security, res), "payment", corpus))
        assert [row["verdict"] for row in pair] == ["off-topic", "off-topic"], (
            "two chunks sharing no query term answer %r"
            % ([row["verdict"] for row in pair],))
        assert s.by_verdict(pair)["off-topic"] == ("res-1:1.1", "sec-1:2.1"), (
            "by_verdict's tuple is %r, and each verdict's ids are sorted"
            % (s.by_verdict(pair)["off-topic"],))

    def _s6_refusals(s, index, corpus):
        paid = _s6_chunk(index, "msa-3:3.2")
        before = corpus.stats()
        _refuses(ValueError, "a chunk id where a chunk record belongs",
                 lambda: s.critique(("msa-3:3.2",), "payment", corpus),
                 names=("msa-3:3.2",))
        _refuses(ValueError, "a chunks argument that is not a sequence of records",
                 lambda: s.critique("msa-3:3.2", "payment", corpus), names=("str",))
        _refuses(ValueError, "a chunk record with no text",
                 lambda: s.critique(({"doc": "msa-3", "clause": "3.2", "refs": ()},),
                                    "payment", corpus), names=("3.2", "text"))
        refused = corpus.stats()
        assert refused == before, (
            "a shape the stage will not accept asked the corpus something: %r then %r"
            % (before, refused))
        _refuses(ValueError, "a chunk of a document the corpus does not hold",
                 lambda: s.critique((dict(paid, doc="nope"),), "payment", corpus),
                 names=("nope",))
        after = corpus.stats()
        assert after["lookups"] == before["lookups"] + 2, (
            "the unknown document is refused after the subjects and the document were "
            "asked for, and lookups went %r then %r" % (before["lookups"],
                                                        after["lookups"]))
        assert after["analyses"] == before["analyses"] + 1, (
            "the unknown document is refused after the query was analyzed once, and "
            "analyses went %r then %r" % (before["analyses"], after["analyses"]))

    def _s6_ledger(s, index, corpus):
        paid = _s6_chunk(index, "msa-3:3.2")
        lic = _s6_chunk(index, "lic-2:6.1")
        before = corpus.stats()
        s.critique((paid,), "invoice payment", corpus)
        after = corpus.stats()
        assert after["lookups"] == before["lookups"] + 3, (
            "one live chunk costs the subjects, its own document and its document's clause "
            "index, and lookups went %r then %r" % (before["lookups"], after["lookups"]))
        assert after["analyses"] == before["analyses"] + 2, (
            "one live chunk analyzes the query once and its own text once, and analyses "
            "went %r then %r" % (before["analyses"], after["analyses"]))
        before = after
        s.critique((lic,), "liability", corpus)
        after = corpus.stats()
        assert after["lookups"] == before["lookups"] + 2, (
            "a superseded chunk is decided by its document alone, one lookup fewer than a "
            "live one, and lookups went %r then %r" % (before["lookups"],
                                                       after["lookups"]))
        assert after["analyses"] == before["analyses"] + 1, (
            "a superseded chunk's own text is never analyzed, and analyses went %r then %r"
            % (before["analyses"], after["analyses"]))
        before = after
        assert s.critique((), "payment", corpus) == (), (
            "a critique of no chunks is not the empty answer")
        assert corpus.stats() == before, (
            "a critique of no chunks asked the corpus something: %r then %r"
            % (before, corpus.stats()))

    def _s6_workload(s, stage03, world):
        """One whole pass of the stage over fixtures built here, as one tuple."""
        corpus = world.Corpus.build(7)
        index = stage03.Index.build(corpus)
        lic = _s6_chunk(index, "lic-2:6.1")
        paid = _s6_chunk(index, "msa-3:3.2")
        invoiced = _s6_chunk(index, "sow-1:4.1")
        dangling = _s6_chunk(index, "dpa-1:2.3")
        res = _s6_chunk(index, "res-1:1.1")
        security = _s6_chunk(index, "sec-1:2.1")
        mixed = s.critique((lic, paid, dangling, res), "payment liability", corpus)
        return (mixed, s.survivors(mixed), s.by_verdict(mixed),
                s.critique((paid, invoiced), "payment", corpus),
                s.critique((paid, paid), "payment", corpus),
                s.critique((security, paid), "", corpus),
                s.critique((), "payment", corpus))

    def _s6_twice(s, stage03, world):
        one = _s6_workload(s, stage03, world)
        two = _s6_workload(s, stage03, world)
        assert one == two, (
            "two runs of one workload critiqued differently, so a critique is not a "
            "function of its inputs")

    import corpus as world
    import stage_01 as stage01
    import stage_03 as stage03
    import stage_06 as s
    corpus = world.Corpus.build(7)
    index = stage03.Index.build(corpus)
    _s6_constants(s, world)
    _s6_catalog(stage01, corpus, index)
    _s6_stale(s, index, corpus)
    _s6_conflict(s, index, corpus)
    _s6_unresolvable(s, index, corpus)
    _s6_vocabulary(s, index, corpus)
    _s6_survivors(s, index, corpus)
    _s6_refusals(s, index, corpus)
    _s6_ledger(s, index, corpus)
    _s6_twice(s, stage03, world)

# --- stage 7 -----------------------------------------------------------------------
def check_7():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "agentic-retrieval-from-scratch"

    S7_CLAIM_KEYS = ("text", "cite")

    S7_ANSWER_KEYS = ("query", "claims", "citations", "grounding_bp", "abstained",
                      "reason")

    S7_ABSTENTIONS = ("nothing-survived", "conflict-unresolved", "not-grounding",
                      "ambiguous-cite")

    S7_CITATION_PROBLEMS = ("missing-cite", "unknown-cite", "ambiguous-cite",
                            "abstained-with-claims")

    S7_GROUNDING_MIN_BP = 5000

    S7_FULL_BP = 10000

    S7_DOC = "msa-3"

    S7_DUP = "msa-3:5.2"

    def _repo(start=None):
        for candidate_start in (os.environ.get("K1_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "course.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set K1_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked
        against the message: an exception of the right family raised for the wrong
        reason is not the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return refused
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    S7_QUERY = "payment within interest window"

    S7_ANSWER_TEXT = "Payment is due within thirty days of a valid invoice."

    S7_OTHER_TEXT = "Overdue amounts carry interest each month."

    S7_OFF_TEXT = "The Supplier's personnel are not employees of the Customer."

    S7_DUP_TEXT = "Payment is due within thirty days."

    S7_FIRST_TEXT = "A notice is effective on delivery."

    def _distinct(terms):
        """The terms once each, in first-appearance order — the check's own reading."""
        found = []
        for term in terms:
            if term not in found:
                found.append(term)
        return tuple(found)

    def _chunk(doc, clause, text, level=2):
        """One `CHUNK_KEYS` record, in order, as the chunker of stage 1 writes them."""
        return {"doc": doc, "clause": clause, "level": level, "text": text,
                "refs": (), "defines": ()}

    def _critique(chunk, verdict, reason="a reason"):
        """One `CRITIQUE_KEYS` row, in order, as the critique of stage 6 writes them."""
        return {"chunk": chunk, "verdict": verdict, "reason": reason, "against": None}

    def _analyses(corpus):
        """How many analyses the library's own log says it was asked for."""
        return corpus.stats()["analyses"]

    def _share(corpus, query, chunks):
        """The check's own grounding: distinct query terms present, in basis points."""
        wanted = _distinct(corpus.terms(query))
        if not wanted:
            return 0
        held = []
        for chunk in chunks:
            held.extend(corpus.terms(chunk["text"]))
        return len([term for term in wanted if term in held]) * S7_FULL_BP // len(wanted)

    def _s7_fixtures():
        """The three chunks and the three rows every answer question is asked about."""
        a = _chunk(S7_DOC, "3.1", S7_ANSWER_TEXT)
        b = _chunk(S7_DOC, "3.2", S7_OTHER_TEXT)
        c = _chunk(S7_DOC, "4.1", S7_OFF_TEXT)
        return a, b, c

    def _s7_constants(s):
        assert tuple(s.CLAIM_KEYS) == S7_CLAIM_KEYS, (
            "a claim is `text` then `cite`, in that order, and it is %r"
            % (tuple(s.CLAIM_KEYS),))
        assert tuple(s.ANSWER_KEYS) == S7_ANSWER_KEYS, (
            "an answer's six fields come in the pinned order, and they are %r"
            % (tuple(s.ANSWER_KEYS),))
        assert tuple(s.ABSTENTIONS) == S7_ABSTENTIONS, (
            "the four abstention reasons are a closed vocabulary in the order the "
            "abstention is decided in, and they are %r" % (tuple(s.ABSTENTIONS),))
        assert tuple(s.CITATION_PROBLEMS) == S7_CITATION_PROBLEMS, (
            "the four citation faults are reported in this order, and the stage's are "
            "%r" % (tuple(s.CITATION_PROBLEMS),))
        assert s.GROUNDING_MIN_BP == S7_GROUNDING_MIN_BP, (
            "the grounding floor is %d basis points and the stage says %r"
            % (S7_GROUNDING_MIN_BP, s.GROUNDING_MIN_BP))

    def _s7_grounding(s, world):
        corpus = world.Corpus.build(7)
        repeated = "payment payment within"
        terms = corpus.terms(repeated)
        assert len(terms) != len(_distinct(terms)), (
            "the fixture repeats a term, so a share counted over tokens differs from a "
            "share counted over distinct terms")
        only = _chunk(S7_DOC, "3.1", "payment")
        before = _analyses(corpus)
        got = s.grounding_bp(corpus, repeated, (only,))
        after = _analyses(corpus)
        assert got == S7_GROUNDING_MIN_BP, (
            "a term the question repeats is one term, so half of two distinct terms is "
            "%d basis points and it was %r" % (S7_GROUNDING_MIN_BP, got))
        assert after - before == 2, (
            "one analysis of the query and one of its single chunk is two analyses, and "
            "the library was asked %d times" % (after - before,))
        a, b, c = _s7_fixtures()
        assert s.grounding_bp(corpus, S7_QUERY, (a,)) == S7_GROUNDING_MIN_BP, (
            "`payment` and `within` of four distinct query terms is half the question, "
            "and it answered %r" % (s.grounding_bp(corpus, S7_QUERY, (a,)),))
        assert s.grounding_bp(corpus, S7_QUERY, (a, b, c)) == 7500, (
            "three of the four distinct query terms appear across the chunks, which is "
            "7500 basis points and it answered %r"
            % (s.grounding_bp(corpus, S7_QUERY, (a, b, c)),))
        assert s.grounding_bp(corpus, S7_QUERY, (a, b, c)) == _share(corpus, S7_QUERY,
                                                                     (a, b, c)), (
            "grounding is the share of the query's distinct analyzed terms the chunks "
            "carry, recomputed by this check and by the stage")
        assert s.grounding_bp(corpus, S7_QUERY, (c,)) == 0, (
            "a chunk that carries none of the query's terms grounds nothing, and it "
            "answered %r" % (s.grounding_bp(corpus, S7_QUERY, (c,)),))
        before = _analyses(corpus)
        assert s.grounding_bp(corpus, "", (a, b)) == 0, (
            "a query with no terms at all is not a share of nothing, it is zero")
        assert _analyses(corpus) - before == 1, (
            "a query with no terms is analyzed once and the chunks not at all, so the "
            "library was asked %d times" % (_analyses(corpus) - before,))
        before = _analyses(corpus)
        _refuses(world.CorpusError, "a query that is not a string",
                 lambda: s.grounding_bp(corpus, 7, (a,)), names=("7",))
        assert _analyses(corpus) == before, (
            "a refused grounding asked the library to analyze anyway: %r"
            % (corpus.stats(),))
        _refuses(world.CorpusError, "chunks that are not a sequence of chunks",
                 lambda: s.grounding_bp(corpus, S7_QUERY, "chunks"), names=("chunks",))

    def _s7_answer(s, world):
        corpus = world.Corpus.build(7)
        a, b, c = _s7_fixtures()
        chunks = (a, b, c)
        exact = s.answer(corpus, S7_QUERY, chunks,
                         (_critique("msa-3:3.1", "supported"),
                          _critique("msa-3:3.2", "off-topic"),
                          _critique("msa-3:4.1", "off-topic")),
                         S7_GROUNDING_MIN_BP)
        assert tuple(exact) == S7_ANSWER_KEYS, (
            "an answered run holds the six fields in the pinned order, and it holds %r"
            % (tuple(exact),))
        assert exact["query"] == S7_QUERY, (
            "the answer echoes the query it was asked, and it echoed %r"
            % (exact["query"],))
        assert exact["abstained"] is False and exact["reason"] is None, (
            "a run grounded at exactly the floor answers, and it abstained for %r"
            % (exact["reason"],))
        assert exact["grounding_bp"] == S7_GROUNDING_MIN_BP, (
            "exactly the minimum is grounded, so the run reports %d and it reported %r"
            % (S7_GROUNDING_MIN_BP, exact["grounding_bp"]))
        assert exact["citations"] == ("msa-3:3.1",), (
            "one survivor earns one citation, and the run cited %r"
            % (exact["citations"],))
        assert exact["claims"] == ({"text": S7_ANSWER_TEXT, "cite": "msa-3:3.1"},), (
            "a claim quotes the surviving chunk's own text verbatim and cites its id, "
            "and the run claimed %r" % (exact["claims"],))
        assert tuple(exact["claims"][0]) == S7_CLAIM_KEYS, (
            "a claim's two fields are `text` then `cite`, and this one holds %r"
            % (tuple(exact["claims"][0]),))
        ordered = s.answer(corpus, S7_QUERY, chunks,
                           (_critique("msa-3:4.1", "supported"),
                            _critique("msa-3:3.1", "supported"),
                            _critique("msa-3:3.2", "supported")), 0)
        assert ordered["citations"] == ("msa-3:4.1", "msa-3:3.1", "msa-3:3.2"), (
            "citations come in the survivors' order and are never sorted, and this run "
            "cited %r" % (ordered["citations"],))
        assert tuple(claim["text"] for claim in ordered["claims"]) == (
            S7_OFF_TEXT, S7_ANSWER_TEXT, S7_OTHER_TEXT), (
            "each claim quotes the chunk its citation names, and the run claimed %r"
            % (ordered["claims"],))
        assert ordered["grounding_bp"] == 7500, (
            "three of the four distinct query terms across the survivors is 7500, and "
            "the run reported %r" % (ordered["grounding_bp"],))
        assert s.check_citations(ordered, chunks) == (), (
            "an answer this stage built quotes and cites what it was given, and the "
            "scanner found %r" % (s.check_citations(ordered, chunks),))
        fresh = world.Corpus.build(7)
        before = _analyses(fresh)
        s.answer(fresh, S7_QUERY, (a,), (_critique("msa-3:3.1", "supported"),),
                 S7_GROUNDING_MIN_BP)
        assert _analyses(fresh) - before == 2, (
            "the grounding an answer reports is measured over its survivors, so one "
            "answer over one survivor analyzes the query once and that chunk once, and "
            "the library was asked %d times" % (_analyses(fresh) - before,))

        short = s.answer(corpus, S7_QUERY, chunks,
                         (_critique("msa-3:3.1", "off-topic"),
                          _critique("msa-3:3.2", "supported"),
                          _critique("msa-3:4.1", "off-topic")), S7_GROUNDING_MIN_BP)
        assert short["abstained"] is True, (
            "a run below the floor abstains, and it answered %r" % (short,))
        assert short["query"] == S7_QUERY, (
            "a refused run echoes the query it was asked, and it echoed %r"
            % (short["query"],))
        assert short["reason"] == "not-grounding: grounding 2500bp < 5000bp", (
            "a refusal names its own reason from the vocabulary and both numbers, the "
            "share it measured and the floor, and it said %r" % (short["reason"],))
        assert short["grounding_bp"] == 2500, (
            "one surviving term of four is 2500 basis points; over every retrieved "
            "chunk it would be 7500, and the run reported %r" % (short["grounding_bp"],))
        assert short["claims"] == () and short["citations"] == (), (
            "an abstention holds no claims and no citations, and it held %r"
            % (short["claims"],))
        assert s.check_citations(short, chunks) == (), (
            "an abstention this stage built carries nothing, and the scanner found %r"
            % (s.check_citations(short, chunks),))

        nothing = s.answer(corpus, S7_QUERY, chunks,
                           (_critique("msa-3:3.1", "off-topic"),
                            _critique("msa-3:3.2", "stale")), 0)
        assert nothing["reason"] == "nothing-survived", (
            "a critique that kept nothing is the first reason of all, and it said %r"
            % (nothing["reason"],))
        assert nothing["grounding_bp"] == 0, (
            "no survivors carry no terms, so the run measured 0 and it reported %r"
            % (nothing["grounding_bp"],))
        conflict = s.answer(corpus, S7_QUERY, chunks,
                            (_critique("msa-3:3.1", "supported"),
                             _critique("msa-3:3.2", "conflicting")), 0)
        assert conflict["reason"] == "conflict-unresolved", (
            "a conflict the critiques hold is not answered from either side, even when "
            "a chunk survived, and the run said %r" % (conflict["reason"],))
        assert conflict["claims"] == () and conflict["citations"] == (), (
            "a run that abstained for a conflict claims nothing, and it claimed %r"
            % (conflict["claims"],))

        d1 = _chunk(S7_DOC, "5.2", S7_DUP_TEXT)
        d2 = _chunk(S7_DOC, "5.2", S7_FIRST_TEXT)
        ambiguous = s.answer(corpus, S7_QUERY, (d1, d2),
                             (_critique("msa-3:5.2", "supported"),), 0)
        assert ambiguous["reason"] == "ambiguous-cite", (
            "a surviving id the input holds twice may not be cited as if it were one, "
            "and the run said %r" % (ambiguous["reason"],))
        assert ambiguous["grounding_bp"] == 5000, (
            "the grounding of an ambiguous citation is measured over the first chunk "
            "the input holds for that id, which is 5000 here, and the run reported %r"
            % (ambiguous["grounding_bp"],))
        low = s.answer(corpus, S7_QUERY, (d2, d1),
                       (_critique("msa-3:5.2", "supported"),), S7_GROUNDING_MIN_BP)
        assert low["reason"] == "ambiguous-cite", (
            "an unmakeable citation is decided before the arithmetic of grounding, and "
            "the run said %r" % (low["reason"],))
        assert low["grounding_bp"] == 0, (
            "the first chunk the input holds for the duplicated id is the one with no "
            "query terms, so the run measured 0 and it measured %r"
            % (low["grounding_bp"],))
        both = s.answer(corpus, S7_QUERY, (d1, d2),
                        (_critique("msa-3:5.2", "conflicting"),
                         _critique("msa-3:5.2", "supported")), 0)
        assert both["reason"] == "conflict-unresolved", (
            "a conflict is decided before an ambiguous citation, and the run said %r"
            % (both["reason"],))

        before = _analyses(corpus)
        _refuses(world.CorpusError, "a query that is not a string",
                 lambda: s.answer(corpus, 7, chunks, (), 0), names=("7",))
        assert _analyses(corpus) == before, (
            "a refused answer asked the library to analyze anyway: %r" % (corpus.stats(),))
        _refuses(world.CorpusError, "a minimum that is not a whole number",
                 lambda: s.answer(corpus, S7_QUERY, chunks,
                                  (_critique("msa-3:3.1", "supported"),), "5000"),
                 names=("5000",))
        _refuses(world.CorpusError, "a minimum that is a bool",
                 lambda: s.answer(corpus, S7_QUERY, chunks,
                                  (_critique("msa-3:3.1", "supported"),), True),
                 names=("True",))
        _refuses(world.CorpusError, "a survivor the input chunks do not hold",
                 lambda: s.answer(corpus, S7_QUERY, chunks,
                                  (_critique("msa-3:9.9", "supported"),), 0),
                 names=("msa-3:9.9",))
        blind = {"doc": S7_DOC, "clause": "3.1", "level": 2, "text": None, "refs": (),
                 "defines": ()}
        before = _analyses(corpus)
        _refuses(world.CorpusError, "a chunk that carries no text",
                 lambda: s.answer(corpus, S7_QUERY, (blind,),
                                  (_critique("msa-3:3.1", "supported"),), 0),
                 names=("None",))
        assert _analyses(corpus) - before == 1, (
            "a refused answer asks the library for the query's terms and never for the "
            "text of a chunk it cannot quote, so one analysis and it asked for %d"
            % (_analyses(corpus) - before,))

    def _s7_scanner(s, world):
        a, b, c = _s7_fixtures()
        d1 = _chunk(S7_DOC, "5.2", S7_DUP_TEXT)
        d2 = _chunk(S7_DOC, "5.2", S7_FIRST_TEXT)
        chunks = (a, b, c, d1, d2)
        clean = {"query": S7_QUERY, "grounding_bp": S7_GROUNDING_MIN_BP,
                 "claims": ({"text": S7_ANSWER_TEXT, "cite": "msa-3:3.1"},),
                 "citations": ("msa-3:3.1",), "abstained": False, "reason": None}
        assert s.check_citations(clean, chunks) == (), (
            "a claim that quotes a chunk it was given and cites it in its own "
            "citations is clean, and the scanner found %r"
            % (s.check_citations(clean, chunks),))
        empty = {"query": S7_QUERY, "claims": (), "citations": (), "grounding_bp": 0,
                 "abstained": True, "reason": "nothing-survived"}
        assert s.check_citations(empty, chunks) == (), (
            "an abstention that kept no claims is clean, and the scanner found %r"
            % (s.check_citations(empty, chunks),))
        broken = {"query": S7_QUERY, "grounding_bp": 0,
                  "claims": ({"text": "one", "cite": ""},
                             {"text": "two", "cite": "msa-3:5.5"}),
                  "citations": ("msa-3:9.9", "msa-3:5.2", "msa-3:3.1"),
                  "abstained": True, "reason": "not-grounding"}
        got = s.check_citations(broken, chunks)
        want = (("missing-cite", ""), ("missing-cite", "msa-3:5.5"),
                ("unknown-cite", "msa-3:9.9"), ("ambiguous-cite", "msa-3:5.2"),
                ("abstained-with-claims", "not-grounding"))
        assert got == want, (
            "the scanner reports the four faults grouped in `CITATION_PROBLEMS` order, "
            "each naming its offender, and it reported %r" % (got,))
        assert isinstance(got, tuple), (
            "a scan answers a tuple of pairs rather than a %s" % (type(got).__name__,))
        stray = {"query": S7_QUERY, "grounding_bp": 0,
                 "claims": ({"text": "one", "cite": "msa-3:9.9"},),
                 "citations": ("msa-3:9.9",), "abstained": False, "reason": None}
        assert s.check_citations(stray, chunks) == (("unknown-cite", "msa-3:9.9"),), (
            "a citation the input chunks do not hold is `unknown-cite` even when the "
            "claim's own citation list agrees with it, and the scanner found %r"
            % (s.check_citations(stray, chunks),))
        typed = {"query": S7_QUERY, "grounding_bp": 0,
                 "claims": ({"text": "one", "cite": None},),
                 "citations": ("msa-3:3.1",), "abstained": False, "reason": None}
        assert s.check_citations(typed, chunks) == (("missing-cite", ""),), (
            "a cite that is not a chunk id at all is a missing one, and the scanner "
            "found %r" % (s.check_citations(typed, chunks),))
        sloppy = {"query": S7_QUERY, "grounding_bp": 0,
                  "claims": ({"text": "one", "cite": "msa-3:3.1"},),
                  "citations": ("msa-3:3.1",), "abstained": True, "reason": None}
        assert s.check_citations(sloppy, chunks) == (("abstained-with-claims", ""),), (
            "an abstention that kept its claims is a fault even when it names no "
            "reason, and the scanner found %r" % (s.check_citations(sloppy, chunks),))
        _refuses(world.CorpusError, "an answer that is not a mapping",
                 lambda: s.check_citations("answer", chunks), names=("answer",))
        _refuses(world.CorpusError, "a claim that is not a mapping",
                 lambda: s.check_citations({"claims": ("a claim",), "citations": ()},
                                           chunks), names=("a claim",))
        _refuses(world.CorpusError, "chunks that are not a sequence",
                 lambda: s.check_citations(clean, "chunks"), names=("chunks",))

    def _s7_together(s, stage1, stage6, world):
        """One pass over the real pipeline: stage 1 chunked, stage 6 critiqued."""
        corpus = world.Corpus.build(7)
        chunks, problems = stage1.chunk(corpus.document(S7_DOC))
        assert chunks, ("the fixture's document chunks into clauses at all: %r"
                        % (problems,))
        by_id = {}
        for chunk in chunks:
            by_id.setdefault(stage1.chunk_id(chunk), chunk)
        query = "How long after a valid invoice is payment due?"
        rows = stage6.critique(chunks, query, corpus)
        ans = s.answer(corpus, query, chunks, rows, S7_GROUNDING_MIN_BP)
        assert tuple(ans) == S7_ANSWER_KEYS, (
            "a real pass answers the six fields in order, and it answered %r"
            % (tuple(ans),))
        if ans["abstained"]:
            assert ans["reason"] in S7_ABSTENTIONS or ans["reason"].startswith(
                "not-grounding: grounding "), (
                "an abstention's reason is one of the pinned vocabulary — the "
                "not-grounding one naming both its numbers — and it said %r"
                % (ans["reason"],))
            assert ans["claims"] == () and ans["citations"] == (), (
                "a real abstention carries no claims, and it carried %r"
                % (ans["claims"],))
        else:
            assert ans["citations"] == stage6.survivors(rows), (
                "the survivors are stage 6's own, in stage 6's own order, and this "
                "answer cited %r" % (ans["citations"],))
            for claim, cid in zip(ans["claims"], ans["citations"]):
                assert claim["cite"] == cid, (
                    "a claim cites the survivor it answers from, and %r cites %r"
                    % (claim, cid))
                assert claim["text"] == by_id[cid]["text"], (
                    "a claim quotes the chunk's own text verbatim, and %r does not"
                    % (claim,))
        assert s.check_citations(ans, chunks) == (), (
            "the answer the real pipeline built scans clean, and the scanner found %r"
            % (s.check_citations(ans, chunks),))

    def _s7_workload(s, world):
        """One whole pass of this stage over fixtures built here, as one tuple."""
        corpus = world.Corpus.build(7)
        a, b, c = _s7_fixtures()
        chunks = (a, b, c)
        d1 = _chunk(S7_DOC, "5.2", S7_DUP_TEXT)
        d2 = _chunk(S7_DOC, "5.2", S7_FIRST_TEXT)
        answered = s.answer(corpus, S7_QUERY, chunks,
                            (_critique("msa-3:3.1", "supported"),
                             _critique("msa-3:3.2", "off-topic"),
                             _critique("msa-3:4.1", "off-topic")),
                            S7_GROUNDING_MIN_BP)
        refused = s.answer(corpus, S7_QUERY, chunks,
                           (_critique("msa-3:4.1", "supported"),),
                           S7_GROUNDING_MIN_BP)
        ambiguous = s.answer(corpus, S7_QUERY, (d1, d2),
                             (_critique("msa-3:5.2", "supported"),), 0)
        return (answered, refused, ambiguous,
                s.check_citations(answered, chunks),
                s.check_citations(refused, chunks),
                s.grounding_bp(corpus, S7_QUERY, chunks),
                s.grounding_bp(corpus, "payment payment within", (a,)))

    def _s7_twice(s, world):
        one = _s7_workload(s, world)
        two = _s7_workload(s, world)
        assert one == two, (
            "two runs of one workload answered differently, so a run is not a function "
            "of its inputs")

    import corpus as world
    import stage_01 as stage1
    import stage_06 as stage6
    import stage_07 as s
    _s7_constants(s)
    _s7_grounding(s, world)
    _s7_answer(s, world)
    _s7_scanner(s, world)
    _s7_together(s, stage1, stage6, world)
    _s7_twice(s, world)

# --- stage 8 -----------------------------------------------------------------------
def check_8():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "agentic-retrieval-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("K1_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "course.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set K1_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked
        against the message: an exception of the right family raised for the wrong
        reason is not the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return refused
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    _C8_NONSENSE = ("zzz", "qqq", "vvv", "www", "xxx", "yyy", "uuu", "iii", "ooo",
                    "ppp", "aaa", "sss")

    _C8_ROUND_CENTS = 21

    _C8_ROUND_KEYS = ("round", "query", "rewrites", "retrieved", "survivors",
                      "cost_cents")

    _C8_LOOP_KEYS = ("question", "answer", "rounds", "cost_cents", "stopped", "reason")

    _C8_STOPS = ("answered", "abstained", "budget", "round-cap", "repeat")

    _C8_LIMIT = 5

    def _c8_own(exc, what, call, names=()):
        """A refusal this stage makes itself, not one the customer's world made for it."""
        refused = _refuses(exc, what, call, names=names)
        message = str(refused)
        assert not message.startswith("meter: ") and not message.startswith("corpus: "), (
            "%s was refused by the customer's library rather than judged by the stage: %r"
            % (what, message))
        return refused

    def _c8_question(qid, text, expected=(), conversation=()):
        """One `QUESTION_KEYS` record, the way the customer's own library spells one."""
        return {"qid": qid, "text": text, "expected": tuple(expected),
                "conversation": tuple({"speaker": speaker, "text": turn}
                                      for speaker, turn in conversation)}

    def _c8_book(world):
        """The customer's library and an index over it, both built from the world."""
        import stage_03
        book = world.Corpus.build(7)
        return book, stage_03.Index.build(book)

    def _c8_slot(book, index):
        """A chunk id the fixtures may expect, from a document the library still serves."""
        import stage_01
        for chunk in index.chunks:
            if book.document(chunk["doc"])["superseded_by"] is None:
                return stage_01.chunk_id(chunk)
        raise AssertionError("the customer's corpus holds no clause that is still in force")

    def _c8_run(s, book, index, billing, question, limit=_C8_LIMIT, budget=1000, cap=4,
                tick=0, before=()):
        """One `ask` and the meter it charged, with whatever the caller spent first."""
        meter = billing.Meter()
        for kind, units in before:
            meter.charge(kind, units, 0)
        return s.ask(index, book, meter, question, tick, limit, budget, cap), meter

    def _c8_abstain(book, index):
        """A question the loop can neither answer nor improve: one round, then abstained."""
        return _c8_question("f-abstain", " ".join(_C8_NONSENSE[:3]),
                            (_c8_slot(book, index),))

    def _c8_repeat(book, index):
        """A question one rewrite changes and a second cannot: the loop repeats itself."""
        return _c8_question("f-repeat", "it " + " ".join(_C8_NONSENSE),
                            (_c8_slot(book, index),),
                            (("auditor", "The agreement governs deletion termination."),))

    def _c8_acronym(book, index):
        """A question whose only fix is an acronym, so every rewrite changes its text."""
        return _c8_question("f-acronym",
                            sorted(book.glossary)[0] + " " + " ".join(_C8_NONSENSE),
                            (_c8_slot(book, index),))

    def _c8_answered(s, book, index, billing):
        """A clause of the customer's corpus that a round of the loop itself answers."""
        import stage_01
        for chunk in index.chunks:
            if book.document(chunk["doc"])["superseded_by"] is not None:
                continue
            question = _c8_question("f-answered", chunk["text"],
                                    (stage_01.chunk_id(chunk),))
            loop, _meter = _c8_run(s, book, index, billing, question)
            if loop["stopped"] == "answered":
                return question, loop
        raise AssertionError("no clause of the customer's corpus is answered by its own text")

    def _c8_constants(s):
        assert tuple(s.ROUND_KEYS) == _C8_ROUND_KEYS, (
            "a round carries %r, not %r" % (tuple(s.ROUND_KEYS), _C8_ROUND_KEYS))
        assert tuple(s.LOOP_KEYS) == _C8_LOOP_KEYS, (
            "a loop carries %r, not %r" % (tuple(s.LOOP_KEYS), _C8_LOOP_KEYS))
        assert tuple(s.STOPS) == _C8_STOPS, (
            "the closed vocabulary of stops is %r, not %r" % (tuple(s.STOPS), _C8_STOPS))
        assert s.RETRIEVE_UNITS == 1, (
            "a round charges %r units of retrieval" % (s.RETRIEVE_UNITS,))
        assert s.RERANK_UNITS == 1, (
            "a round charges %r units of reranking" % (s.RERANK_UNITS,))
        assert s.CRITIQUE_UNITS == 1, (
            "a round charges %r units of critique" % (s.CRITIQUE_UNITS,))
        assert s.GENERATE_UNITS == 1, (
            "a round charges %r units of generation" % (s.GENERATE_UNITS,))
        assert s.DEFAULT_LIMIT == 5, (
            "the default retrieval width is %r, not 5" % (s.DEFAULT_LIMIT,))

    def _c8_shape(s, world, billing):
        book, index = _c8_book(world)
        fixture = _c8_abstain(book, index)
        loop, meter = _c8_run(s, book, index, billing, fixture)
        assert tuple(loop) == _C8_LOOP_KEYS, (
            "the loop carries %r, not %r" % (tuple(loop), _C8_LOOP_KEYS))
        assert loop["question"] == "f-abstain", (
            "the loop names the question %r" % (loop["question"],))
        assert loop["stopped"] == "abstained", (
            "an unanswerable, unrewritable question stops the loop %r" % (loop["stopped"],))
        assert loop["reason"] == "nothing-survived", (
            "the stop's reason is %r, not the answer's own" % (loop["reason"],))
        assert loop["cost_cents"] == _C8_ROUND_CENTS, (
            "one round cost %r cents" % (loop["cost_cents"],))
        assert loop["answer"]["abstained"] is True, (
            "the loop handed back an answer that did not abstain: %r" % (loop["answer"],))
        assert loop["answer"]["reason"] == "nothing-survived", (
            "the answer's own reason was lost: %r" % (loop["answer"]["reason"],))
        assert s.rounds_of(loop) == loop["rounds"], (
            "rounds_of answered something other than the loop's rounds")
        assert len(loop["rounds"]) == 1, (
            "the loop ran %d rounds and there was nothing to rewrite" % (len(loop["rounds"]),))
        round0 = loop["rounds"][0]
        assert tuple(round0) == _C8_ROUND_KEYS, (
            "a round carries %r, not %r" % (tuple(round0), _C8_ROUND_KEYS))
        assert round0["round"] == 0, (
            "the first round is numbered %r" % (round0["round"],))
        assert round0["query"] == fixture["text"], (
            "round 0 searched %r rather than the question's own text" % (round0["query"],))
        assert round0["rewrites"] == (), (
            "round 0 recorded rewrites it never had: %r" % (round0["rewrites"],))
        assert round0["cost_cents"] == _C8_ROUND_CENTS, (
            "the round's own cost is %r, not the meter's delta" % (round0["cost_cents"],))
        assert round0["survivors"] == (), (
            "a round that answered nothing kept survivors: %r" % (round0["survivors"],))
        assert isinstance(round0["retrieved"], tuple) and round0["retrieved"], (
            "retrieved is %r, not a non-empty tuple of ids" % (round0["retrieved"],))
        assert len(round0["retrieved"]) <= _C8_LIMIT, (
            "the round retrieved %d ids for a limit of %d"
            % (len(round0["retrieved"]), _C8_LIMIT))
        assert all(index.of(cid) is not None for cid in round0["retrieved"]), (
            "the round retrieved ids the index does not hold: %r" % (round0["retrieved"],))
        import stage_03
        import stage_04
        hits = stage_03.search(index, fixture["text"], _C8_LIMIT, "hybrid")
        ranked = stage_04.rerank(index, fixture["text"], hits, _C8_LIMIT)
        assert round0["retrieved"] == tuple(hit["chunk"] for hit in ranked), (
            "the round retrieved %r rather than the reranked hybrid top %r"
            % (round0["retrieved"], tuple(hit["chunk"] for hit in ranked)))
        assert meter.total_cents() == _C8_ROUND_CENTS, (
            "the loop's cost and the meter's total disagree: %r" % (meter.stats(),))

    def _c8_price(s, world, billing):
        book, index = _c8_book(world)
        fixture = _c8_repeat(book, index)
        loop, meter = _c8_run(s, book, index, billing, fixture, before=(("embed", 1),))
        costs = [record["cost_cents"] for record in loop["rounds"]]
        assert costs == [_C8_ROUND_CENTS, _C8_ROUND_CENTS], (
            "each whole round costs %r cents, not %r" % (_C8_ROUND_CENTS, costs))
        assert loop["cost_cents"] == _C8_ROUND_CENTS * len(loop["rounds"]), (
            "the loop's cost %r is not the sum of its rounds" % (loop["cost_cents"],))
        assert meter.total_cents() == 43, (
            "a meter that was already charged one cent holds %d" % (meter.total_cents(),))
        stats = meter.stats()
        assert stats["charges"] == 9, (
            "the meter holds %d charges, not four a round plus one" % (stats["charges"],))
        assert stats["cents"] == 43 and stats["kinds"] == 5, (
            "the customer's own recount is %r" % (stats,))
        by_kind = meter.by_kind()
        for kind in ("retrieve", "rerank", "critique", "generate"):
            assert by_kind[kind]["charges"] == 2 and by_kind[kind]["units"] == 2, (
                "%s was charged %r over two rounds" % (kind, by_kind.get(kind)))

    def _c8_budget(s, world, billing):
        book, index = _c8_book(world)
        abstain = _c8_abstain(book, index)
        repeat = _c8_repeat(book, index)
        loop, meter = _c8_run(s, book, index, billing, abstain, budget=_C8_ROUND_CENTS)
        assert loop["stopped"] == "abstained" and len(loop["rounds"]) == 1, (
            "a budget of exactly one round's cents must pay for that round: %r"
            % (loop["stopped"],))
        assert meter.total_cents() == _C8_ROUND_CENTS, (
            "the round that fit was not charged: %r" % (meter.stats(),))
        loop, meter = _c8_run(s, book, index, billing, abstain, budget=_C8_ROUND_CENTS - 1)
        assert loop["stopped"] == "budget", (
            "a budget one cent short of a round stopped the loop %r" % (loop["stopped"],))
        assert loop["rounds"] == (), (
            "a round that did not fit ran anyway: %r" % (loop["rounds"],))
        assert loop["answer"] is None and loop["cost_cents"] == 0, (
            "a loop that ran nothing holds %r" % (loop,))
        assert meter.total_cents() == 0 and meter.stats()["charges"] == 0, (
            "a round that was not run charged the meter: %r" % (meter.stats(),))
        assert loop["reason"] == "spent 21 of 20", (
            "the reason %r does not name the cents it would have spent and the budget"
            % (loop["reason"],))
        loop, _meter = _c8_run(s, book, index, billing, repeat, budget=40)
        assert loop["stopped"] == "budget" and len(loop["rounds"]) == 1, (
            "a two-round loop under a forty-cent budget stops %r after %d rounds"
            % (loop["stopped"], len(loop["rounds"])))
        assert loop["reason"] == "spent 42 of 40", (
            "the reason %r does not name the cents it would have spent and the budget"
            % (loop["reason"],))
        assert loop["cost_cents"] == _C8_ROUND_CENTS, (
            "the round that fit was not charged: %r" % (loop["cost_cents"],))

    def _c8_cap(s, world, billing):
        book, index = _c8_book(world)
        abstain = _c8_abstain(book, index)
        repeat = _c8_repeat(book, index)
        loop, meter = _c8_run(s, book, index, billing, abstain, cap=0)
        assert loop["stopped"] == "round-cap", (
            "a cap of no rewrites stopped the loop %r" % (loop["stopped"],))
        assert len(loop["rounds"]) == 1, (
            "a cap of no rewrites still ran %d rounds" % (len(loop["rounds"]),))
        assert loop["reason"] == "round cap 0", (
            "the reason %r does not name the cap" % (loop["reason"],))
        assert meter.total_cents() == _C8_ROUND_CENTS, (
            "the single round was not charged: %r" % (meter.stats(),))
        loop, _meter = _c8_run(s, book, index, billing, repeat, cap=1)
        assert loop["stopped"] == "round-cap" and len(loop["rounds"]) == 2, (
            "one rewrite allowed is one round after the first, and this stopped %r after %d"
            % (loop["stopped"], len(loop["rounds"])))
        assert loop["reason"] == "round cap 1", (
            "the reason %r does not name the cap" % (loop["reason"],))
        loop, _meter = _c8_run(s, book, index, billing, repeat, cap=2)
        assert loop["stopped"] == "repeat", (
            "with a second rewrite allowed the loop must repeat rather than cap: %r"
            % (loop["stopped"],))

    def _c8_rewrites(s, world, billing):
        import stage_05
        book, index = _c8_book(world)
        repeat = _c8_repeat(book, index)
        loop, _meter = _c8_run(s, book, index, billing, repeat, cap=4)
        assert loop["stopped"] == "repeat" and len(loop["rounds"]) == 2, (
            "the rewriting question stopped %r after %d rounds"
            % (loop["stopped"], len(loop["rounds"])))
        assert loop["rounds"][0]["rewrites"] == (), (
            "round 0 recorded rewrites it never had: %r" % (loop["rounds"][0]["rewrites"],))
        text, fixes = stage_05.rewrite(book, repeat)
        assert text != repeat["text"] and fixes, (
            "the fixture's premise changed: the rewriter leaves this question alone")
        assert loop["rounds"][1]["query"] == text, (
            "round 1 searched %r rather than the text the rewriter produced"
            % (loop["rounds"][1]["query"],))
        assert loop["rounds"][1]["rewrites"] == tuple(fix["kind"] for fix in fixes), (
            "round 1 recorded %r rather than the kinds of its fixes"
            % (loop["rounds"][1]["rewrites"],))
        assert loop["reason"] == "already tried the query %r" % (text,), (
            "the repeat reason %r does not name the query" % (loop["reason"],))
        acronym = _c8_acronym(book, index)
        loop, meter = _c8_run(s, book, index, billing, acronym, cap=2)
        assert loop["stopped"] == "round-cap" and len(loop["rounds"]) == 3, (
            "an acronym that grows every round capped %r after %d rounds"
            % (loop["stopped"], len(loop["rounds"])))
        kinds = [record["rewrites"] for record in loop["rounds"]]
        assert kinds == [(), ("acronym",), ("acronym",)], (
            "each round records the kinds of the fixes that built it: %r" % (kinds,))
        queries = [record["query"] for record in loop["rounds"]]
        assert len(set(queries)) == len(queries), (
            "a round re-searched a query another round had already searched: %r" % (queries,))
        assert meter.total_cents() == _C8_ROUND_CENTS * 3, (
            "three rounds cost %r cents" % (meter.total_cents(),))

    def _c8_reranked(s, world, billing):
        """A round reports what the reranker put first, not what the search handed it."""
        import stage_01
        import stage_03
        import stage_04
        import stage_06
        book, index = _c8_book(world)
        for chunk in index.chunks:
            if book.document(chunk["doc"])["superseded_by"] is not None:
                continue
            text = chunk["text"]
            hits = stage_03.search(index, text, _C8_LIMIT, "hybrid")
            ranked = stage_04.rerank(index, text, hits, _C8_LIMIT)
            order = tuple(hit["chunk"] for hit in ranked)
            searched = tuple(hit["chunk"] for hit in hits)
            kept = stage_06.survivors(stage_06.critique(
                tuple(index.of(cid) for cid in order), text, book))
            other = stage_06.survivors(stage_06.critique(
                tuple(index.of(cid) for cid in searched), text, book))
            if order == searched or kept == other:
                continue
            question = _c8_question("f-reranked", text, (stage_01.chunk_id(chunk),))
            loop, meter = _c8_run(s, book, index, billing, question)
            round0 = loop["rounds"][0]
            assert round0["retrieved"] == order, (
                "the round retrieved %r rather than what the reranker put first %r"
                % (round0["retrieved"], order))
            assert round0["survivors"] == kept, (
                "the round kept %r rather than the survivors of the reranked order %r"
                % (round0["survivors"], kept))
            assert meter.charges()[0]["kind"] == "retrieve", (
                "the round's first charge is %r" % (meter.charges()[0]["kind"],))
            return
        raise AssertionError("no clause of the customer's corpus separates the two rankings")

    def _c8_answering(s, world, billing):
        book, index = _c8_book(world)
        _question, loop = _c8_answered(s, book, index, billing)
        assert loop["stopped"] == "answered", (
            "a grounded answer stopped the loop %r" % (loop["stopped"],))
        assert loop["reason"] is None, (
            "an answered loop carries the reason %r" % (loop["reason"],))
        assert len(loop["rounds"]) == 1 and loop["cost_cents"] == _C8_ROUND_CENTS, (
            "the answering round is %r" % (loop,))
        answer = loop["answer"]
        assert answer["abstained"] is False and answer["claims"], (
            "the loop answered with %r" % (answer,))
        assert tuple(claim["cite"] for claim in answer["claims"]) == answer["citations"], (
            "the answer's citations are not its claims' own cites: %r" % (answer,))
        assert loop["rounds"][0]["survivors"] == answer["citations"], (
            "the round's survivors %r are not the ids the answer cited %r"
            % (loop["rounds"][0]["survivors"], answer["citations"]))

    def _c8_refuses(s, world, billing):
        book, index = _c8_book(world)
        good = _c8_abstain(book, index)
        meter = billing.Meter()
        _c8_own(ValueError, "a question that is not a record",
                lambda: s.ask(index, book, meter, "question", 0, 5, 40, 4),
                names=("str",))
        _c8_own(ValueError, "a question missing its expected ids",
                lambda: s.ask(index, book, meter, {"qid": "x", "text": "t"}, 0, 5, 40, 4),
                names=("expected",))
        _c8_own(ValueError, "a tick that is not a whole number",
                lambda: s.ask(index, book, meter, good, "0", 5, 40, 4), names=("0",))
        _c8_own(ValueError, "a limit that is a bool",
                lambda: s.ask(index, book, meter, good, 0, True, 40, 4), names=("True",))
        _c8_own(ValueError, "a limit below one",
                lambda: s.ask(index, book, meter, good, 0, 0, 40, 4), names=("0",))
        _c8_own(ValueError, "a budget that is not a whole number",
                lambda: s.ask(index, book, meter, good, 0, 5, "40", 4), names=("40",))
        _c8_own(ValueError, "a budget below zero",
                lambda: s.ask(index, book, meter, good, 0, 5, -1, 4), names=("-1",))
        _c8_own(ValueError, "a round cap below zero",
                lambda: s.ask(index, book, meter, good, 0, 5, 40, -1), names=("-1",))
        assert meter.stats()["charges"] == 0, (
            "a refused call charged the customer's meter %d times"
            % (meter.stats()["charges"],))
        _c8_own(ValueError, "a loop that is not a record",
                lambda: s.rounds_of("loop"), names=("str",))
        _c8_own(ValueError, "a loop missing its rounds",
                lambda: s.rounds_of({}), names=("rounds",))

    def _c8_workload(s, world, billing):
        """The whole workload, as one tuple: every stop the loop can report, priced."""
        book, index = _c8_book(world)
        abstain = _c8_abstain(book, index)
        repeat = _c8_repeat(book, index)
        acronym = _c8_acronym(book, index)
        rows = []
        for fixture, budget, cap in ((abstain, 1000, 4), (repeat, 1000, 4),
                                     (acronym, 1000, 2), (abstain, 20, 4),
                                     (repeat, 40, 4), (repeat, 1000, 1),
                                     (abstain, 1000, 0)):
            loop, meter = _c8_run(s, book, index, billing, fixture, budget=budget, cap=cap)
            rows.append((loop, meter.charges(), meter.stats()))
        _question, answered = _c8_answered(s, book, index, billing)
        rows.append((answered, None, None))
        return tuple(rows)

    def _c8_twice(s, world, billing):
        one = _c8_workload(s, world, billing)
        two = _c8_workload(s, world, billing)
        assert one == two, (
            "two runs of one workload answered differently, so a run is not a function "
            "of its inputs")

    import stage_08 as s
    import corpus as world
    import meter as billing
    _c8_constants(s)
    _c8_shape(s, world, billing)
    _c8_price(s, world, billing)
    _c8_budget(s, world, billing)
    _c8_cap(s, world, billing)
    _c8_rewrites(s, world, billing)
    _c8_reranked(s, world, billing)
    _c8_answering(s, world, billing)
    _c8_refuses(s, world, billing)
    _c8_twice(s, world, billing)

# --- stage 9 -----------------------------------------------------------------------
def check_9():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "agentic-retrieval-from-scratch"

    S9_KEYS = ("kind", "cost_cents", "answered", "hit_bp")

    S9_ROLLUP_KEYS = ("cost_cents", "answered", "cents_per_answer", "delta_cents",
                      "delta_answered")

    S9_MIN_WORTH_IT_GAIN_BP = 400

    S9_LIMIT = 5

    S9_BUDGET_CENTS = 200

    S9_ROUND_CAP = 2

    def _repo(start=None):
        """The repository, named by the world this course always ships.

        `course.py` is assembled after the ten stages are written, so the stage's own
        check cannot wait for it: `corpus.py` sits in the course directory from the
        first minute and names the same repository.
        """
        for candidate_start in (os.environ.get("K1_REPO"), start, os.getcwd(),
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
        raise SystemExit("set K1_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked
        against the message: an exception of the right family raised for the wrong
        reason is not the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return refused
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _s9_first(s):
        """The stage under test answers first, before the earlier stages are asked.

        An untouched template's `NotImplementedError` has to be this check's own
        verdict and not one raised out of stage 3 building an index that stage 9 never
        asked for. A rollup of no rows is a shape no version of this stage can add up.
        """
        _refuses(ValueError, "a rollup of no rows",
                 lambda: s.rollup(()), names=("rollup", "0"))

    def _s9_brought(question, ids):
        """The check's own count of the question's expected ids among `ids`."""
        return sum(1 for expected in question["expected"] if expected in ids)

    def _s9_bp(questions, delivered):
        """The check's own reading of stage 3's coverage rule, in basis points."""
        wanted = sum(len(question["expected"]) for question in questions)
        found = sum(_s9_brought(question, ids)
                    for question, ids in zip(questions, delivered))
        return found * 10000 // wanted if wanted else 0

    def _s9_read(world, meters, three, eight, questions, limit, budget_cents, round_cap):
        """The check's own reading of both rows: one search and one loop per question.

        The naive row is the check's own hybrid search charged once per question plus
        one generation, and its ids are the hits that came back; the checked row is
        stage 8's own loop, charged to the check's own meter, and its ids are the
        citations of the answers that did not abstain.
        """
        corpus = world.Corpus.build(7)
        index = three.Index.build(corpus)
        meter = meters.Meter()
        naive_ids = []
        checked_ids = []
        naive_cents = 0
        checked_cents = 0
        checked_answered = 0
        lost = []
        for tick, question in enumerate(questions):
            start = meter.total_cents()
            meter.charge("retrieve", 1, tick)
            hits = three.search(index, question["text"], limit, "hybrid")
            meter.charge("generate", 1, tick)
            here_naive = tuple(hit["chunk"] for hit in hits)
            here_naive_cents = meter.total_cents() - start
            naive_cents = naive_cents + here_naive_cents
            start = meter.total_cents()
            loop = eight.ask(index, corpus, meter, question, tick, limit,
                             start + budget_cents, round_cap)
            here_checked_cents = meter.total_cents() - start
            checked_cents = checked_cents + here_checked_cents
            answer = loop["answer"]
            here_checked = tuple(answer["citations"]) if answer is not None else ()
            if answer is not None and not answer["abstained"]:
                checked_answered += 1
            naive_ids.append(here_naive)
            checked_ids.append(here_checked)
            if (here_checked_cents > here_naive_cents
                    and _s9_brought(question, here_checked)
                    <= _s9_brought(question, here_naive)):
                lost.append(question["qid"])
        return {
            "naive": {"kind": "naive", "cost_cents": naive_cents,
                      "answered": len(questions),
                      "hit_bp": _s9_bp(questions, naive_ids)},
            "checked": {"kind": "checked", "cost_cents": checked_cents,
                        "answered": checked_answered,
                        "hit_bp": _s9_bp(questions, checked_ids)},
            "lost": tuple(lost),
        }

    def _s9_constants(s, meters):
        """The two row shapes and the noise floor, as the plan pins them."""
        assert tuple(s.BASELINE_KEYS) == S9_KEYS, (
            "a row is `%s`, in that order, and it was %r"
            % ("`, `".join(S9_KEYS), tuple(s.BASELINE_KEYS)))
        assert tuple(s.ROLLUP_KEYS) == S9_ROLLUP_KEYS, (
            "a rollup is `%s`, in the order the arithmetic is written, and it was %r"
            % ("`, `".join(S9_ROLLUP_KEYS), tuple(s.ROLLUP_KEYS)))
        assert s.MIN_WORTH_IT_GAIN_BP == S9_MIN_WORTH_IT_GAIN_BP, (
            "the gain checking has to reach is %d basis points of coverage, and it was %r"
            % (S9_MIN_WORTH_IT_GAIN_BP, s.MIN_WORTH_IT_GAIN_BP))
        assert meters.PRICE_CENTS["retrieve"] == 2, (
            "the customer's own price for a retrieval moved, so this check's arithmetic "
            "is reading a different world")
        assert meters.PRICE_CENTS["generate"] == 12, (
            "the customer's own price for a generation moved, so this check's arithmetic "
            "is reading a different world")

    def _s9_price(s, world, meters, three, eight):
        """Both rows over the customer's own questions, held against the meter's ledger."""
        corpus = world.Corpus.build(7)
        index = three.Index.build(corpus)
        questions = corpus.questions
        meter = meters.Meter()
        rows = s.price(index, corpus, meter, questions, S9_LIMIT, S9_BUDGET_CENTS,
                       S9_ROUND_CAP)
        want = _s9_read(world, meters, three, eight, questions, S9_LIMIT,
                        S9_BUDGET_CENTS, S9_ROUND_CAP)
        assert isinstance(rows, tuple) and len(rows) == 2, (
            "a price answers the naive row and the checked row, and it answered %r"
            % (rows,))
        for position, kind in enumerate(("naive", "checked")):
            row = rows[position]
            assert isinstance(row, dict) and tuple(row.keys()) == S9_KEYS, (
                "the %s row is a `%s` record, and it was %r"
                % (kind, "`, `".join(S9_KEYS), row))
            assert row["kind"] == kind, (
                "the row of a price at position %d is %r, not the %s row — the naive "
                "pipeline is priced first" % (position, row["kind"], kind))
            assert row["cost_cents"] == want[kind]["cost_cents"], (
                "the %s row cost %r cents and the meter's own charges for it were %r"
                % (kind, row["cost_cents"], want[kind]["cost_cents"]))
            assert row["answered"] == want[kind]["answered"], (
                "the %s row answered %r questions and answered %r"
                % (kind, row["answered"], want[kind]["answered"]))
            assert row["hit_bp"] == want[kind]["hit_bp"], (
                "the %s row's coverage is %r basis points and the ids it brought to the "
                "customer are worth %r" % (kind, row["hit_bp"], want[kind]["hit_bp"]))
        naive, checked = rows
        assert naive["answered"] == len(questions), (
            "the naive pipeline abstains nowhere — it has no gate to fail — so its "
            "answered is every question, and it was %r of %d"
            % (naive["answered"], len(questions)))
        each_naive = (meters.PRICE_CENTS["retrieve"] + meters.PRICE_CENTS["generate"])
        assert naive["cost_cents"] == len(questions) * each_naive, (
            "the naive pipeline costs one retrieval and one generation per question, "
            "and it was priced at %r cents" % (naive["cost_cents"],))
        log = meter.charges()
        assert meter.stats()["cents"] == meter.total_cents(), (
            "the meter's own counters disagree with its own log: %r" % (meter.stats(),))
        assert meter.total_cents() == naive["cost_cents"] + checked["cost_cents"], (
            "the two rows' costs are not the meter's own total: %r + %r against %r"
            % (naive["cost_cents"], checked["cost_cents"], meter.total_cents()))
        assert len(log) >= 2 * len(questions), (
            "the naive row charges one retrieval and one generation per question, and "
            "the meter has only %d lines" % (len(log),))
        for tick, _ in enumerate(questions):
            assert log[2 * tick]["kind"] == "retrieve", (
                "question %d's first charge is %r — the naive row retrieves before it "
                "generates" % (tick, log[2 * tick]["kind"]))
            assert log[2 * tick]["tick"] == tick, (
                "question %d was charged at tick %r — the tick is the question's own "
                "position" % (tick, log[2 * tick]["tick"]))
            assert log[2 * tick + 1]["kind"] == "generate", (
                "question %d's second charge is %r, not the generation of its answer"
                % (tick, log[2 * tick + 1]["kind"]))
            assert log[2 * tick + 1]["tick"] == tick, (
                "question %d's generation was charged at tick %r"
                % (tick, log[2 * tick + 1]["tick"]))
        naive_lines = sum(line["cents"] for line in log[:2 * len(questions)])
        assert naive_lines == naive["cost_cents"], (
            "the meter's first %d lines cost %r cents and the naive row reports %r"
            % (2 * len(questions), naive_lines, naive["cost_cents"]))
        checked_lines = sum(line["cents"] for line in log[2 * len(questions):])
        assert checked_lines == checked["cost_cents"], (
            "the meter's own lines after the naive row cost %r cents and the checked "
            "row reports %r" % (checked_lines, checked["cost_cents"]))
        assert meter.total_ticks() == len(questions) - 1, (
            "the last question was charged at tick %d and the meter's highest tick is %r"
            % (len(questions) - 1, meter.total_ticks()))
        tail = questions[:2]
        warmed = meters.Meter()
        warmed.charge("embed", 1, 0)
        held = warmed.total_cents()
        warmed_rows = s.price(index, corpus, warmed, tail, S9_LIMIT, S9_BUDGET_CENTS,
                              S9_ROUND_CAP)
        warmed_want = _s9_read(world, meters, three, eight, tail, S9_LIMIT,
                               S9_BUDGET_CENTS, S9_ROUND_CAP)
        assert warmed_rows[0]["cost_cents"] == warmed_want["naive"]["cost_cents"], (
            "a price against a meter that already holds a customer's charge still prices "
            "its naive row as that row's own delta, %r, and it reported %r"
            % (warmed_want["naive"]["cost_cents"], warmed_rows[0]["cost_cents"]))
        assert warmed_rows[1]["cost_cents"] == warmed_want["checked"]["cost_cents"], (
            "the checked row's cost is its own delta too, %r, and it reported %r"
            % (warmed_want["checked"]["cost_cents"], warmed_rows[1]["cost_cents"]))
        assert warmed.total_cents() == (held + warmed_rows[0]["cost_cents"]
                                        + warmed_rows[1]["cost_cents"]), (
            "a price adds its two rows' costs to what the meter already held: %r cents "
            "against the %r the meter recounts" % (held + warmed_rows[0]["cost_cents"]
                                                  + warmed_rows[1]["cost_cents"],
                                                  warmed.total_cents()))

    def _s9_limit(s, world, meters, three, eight):
        """The limit reaches both rows: the ids in front of the customer move with it."""
        corpus = world.Corpus.build(7)
        index = three.Index.build(corpus)
        questions = corpus.questions
        meter = meters.Meter()
        rows = s.price(index, corpus, meter, questions, 1, S9_BUDGET_CENTS, S9_ROUND_CAP)
        want = _s9_read(world, meters, three, eight, questions, 1, S9_BUDGET_CENTS,
                        S9_ROUND_CAP)
        assert rows[0]["hit_bp"] == want["naive"]["hit_bp"], (
            "a price at a limit of one retrieves one hit per question, and the naive "
            "row's coverage was %r instead of %r"
            % (rows[0]["hit_bp"], want["naive"]["hit_bp"]))
        assert rows[1]["hit_bp"] == want["checked"]["hit_bp"], (
            "a price at a limit of one hands that limit to the loop as well, and the "
            "checked row's coverage was %r instead of %r"
            % (rows[1]["hit_bp"], want["checked"]["hit_bp"]))
        assert rows[0]["answered"] == len(questions), (
            "the naive row answers every question at any limit, and it answered %r"
            % (rows[0]["answered"],))

    def _s9_hand():
        """A question the checked pipeline answers better than the naive one ever could.

        Its text neither names its subject nor carries enough of its own terms to stand
        alone, which is exactly what stage 5 rewrites, so the naive top-5 never holds
        the clause it wants while the checked loop's second round finds it and cites it.
        It is the question `where_it_lost` must not lie about.
        """
        return {"qid": "q-hand", "text": "How long does it have to be?",
                "expected": ("dpa-1:6.1",),
                "conversation": ({"speaker": "auditor",
                                  "text": "Personal Data is deleted on termination, "
                                          "except where 5.1 requires retention."},)}

    def _s9_better(s, world, meters, three, eight):
        """That one question, on its own: paid more for, and answered better, so not lost."""
        questions = (_s9_hand(),)
        corpus = world.Corpus.build(7)
        index = three.Index.build(corpus)
        meter = meters.Meter()
        rows = s.price(index, corpus, meter, questions, S9_LIMIT, S9_BUDGET_CENTS,
                       S9_ROUND_CAP)
        want = _s9_read(world, meters, three, eight, questions, S9_LIMIT,
                        S9_BUDGET_CENTS, S9_ROUND_CAP)
        assert rows[0] == want["naive"], (
            "the naive pipeline never reaches this question's clause, so its coverage is "
            "nothing and it still answers: %r" % (rows[0],))
        assert rows[0]["answered"] == 1 and rows[0]["hit_bp"] == 0, (
            "the naive pipeline answers this question and finds none of what it expects, "
            "and it answered %r with %r basis points"
            % (rows[0]["answered"], rows[0]["hit_bp"]))
        assert rows[0]["hit_bp"] < want["checked"]["hit_bp"], (
            "this question is the one the checking pays off on: the naive row covered %r "
            "and the checked row %r" % (rows[0]["hit_bp"], want["checked"]["hit_bp"]))
        assert rows[1] == want["checked"], (
            "the checked row over this one question is %r, and it was %r"
            % (want["checked"], rows[1]))
        assert rows[1]["cost_cents"] > rows[0]["cost_cents"], (
            "the checked pipeline paid more for this question, %r against %r"
            % (rows[1]["cost_cents"], rows[0]["cost_cents"]))
        aside = meters.Meter()
        assert s.where_it_lost(index, corpus, aside, questions, S9_LIMIT,
                               S9_BUDGET_CENTS, S9_ROUND_CAP) == (), (
            "the checked pipeline paid more for this question and brought the clause the "
            "naive one never did, so it did not lose it")

    def _s9_empty(s, world, meters, three, eight):
        """A price over no questions: two rows of zeros, no charges, and no division."""
        corpus = world.Corpus.build(7)
        index = three.Index.build(corpus)
        meter = meters.Meter()
        rows = s.price(index, corpus, meter, (), S9_LIMIT, S9_BUDGET_CENTS, S9_ROUND_CAP)
        zeroed = ({"kind": "naive", "cost_cents": 0, "answered": 0, "hit_bp": 0},
                  {"kind": "checked", "cost_cents": 0, "answered": 0, "hit_bp": 0})
        assert rows == zeroed, (
            "a price over no questions is two rows of zeros, and it answered %r"
            % (rows,))
        assert meter.charges() == () and meter.total_cents() == 0, (
            "a price over no questions charged the meter %r" % (meter.charges(),))
        summary = s.rollup(rows)
        assert summary == {"cost_cents": 0, "answered": 0, "cents_per_answer": None,
                           "delta_cents": 0, "delta_answered": 0}, (
            "a rollup of nothing answered answers `None` cents per answer rather than "
            "raising or guessing zero, and it answered %r" % (summary,))
        assert s.worth_it(rows) == "within-noise", (
            "a checked row that cost nothing more and covered nothing more is "
            "`within-noise`, and it was %r" % (s.worth_it(rows),))
        aside = meters.Meter()
        assert s.where_it_lost(index, corpus, aside, (), S9_LIMIT, S9_BUDGET_CENTS,
                               S9_ROUND_CAP) == (), (
            "where_it_lost over no questions is an empty answer")
        assert aside.charges() == (), (
            "where_it_lost over no questions charged the meter %r" % (aside.charges(),))

    def _s9_budget(s, world, meters, three, eight):
        """The budget is one question's: it buys a round, or the loop answers nothing."""
        corpus = world.Corpus.build(7)
        index = three.Index.build(corpus)
        questions = corpus.questions
        each_round = sum(meters.PRICE_CENTS[kind]
                         for kind in ("retrieve", "rerank", "critique", "generate"))
        assert each_round == 21, (
            "a round is one retrieval, one rerank, one critique and one generation, 21 "
            "cents, and the world prices it at %r" % (each_round,))
        starved = meters.Meter()
        rows = s.price(index, corpus, starved, questions, S9_LIMIT, 0, S9_ROUND_CAP)
        assert rows[1] == {"kind": "checked", "cost_cents": 0, "answered": 0, "hit_bp": 0}, (
            "a budget of nothing buys no round at all, so the checked row costs nothing, "
            "answers nothing and covers nothing, and it was %r" % (rows[1],))
        assert starved.total_cents() == rows[0]["cost_cents"], (
            "with no budget only the naive row spends, %r cents, and the meter holds %r"
            % (rows[0]["cost_cents"], starved.total_cents()))
        fed = meters.Meter()
        fed_rows = s.price(index, corpus, fed, questions, S9_LIMIT, each_round,
                           S9_ROUND_CAP)
        want = _s9_read(world, meters, three, eight, questions, S9_LIMIT, each_round,
                        S9_ROUND_CAP)
        assert fed_rows[1] == want["checked"], (
            "a budget of exactly one round's price lets every question run exactly one "
            "round: %r against %r" % (fed_rows[1], want["checked"]))
        assert fed_rows[1]["cost_cents"] == each_round * len(questions), (
            "one round a question is %d cents over %d questions, and the checked row "
            "spent %r" % (each_round, len(questions), fed_rows[1]["cost_cents"]))
        assert fed.total_cents() == fed_rows[0]["cost_cents"] + fed_rows[1]["cost_cents"], (
            "the meter's own total is both rows' costs, and it holds %r"
            % (fed.total_cents(),))

    def _s9_lost(s, world, meters, three, eight):
        """The questions the checked pipeline paid more for and answered no better."""
        corpus = world.Corpus.build(7)
        index = three.Index.build(corpus)
        questions = corpus.questions + (_s9_hand(),)
        meter = meters.Meter()
        lost = s.where_it_lost(index, corpus, meter, questions, S9_LIMIT,
                               S9_BUDGET_CENTS, S9_ROUND_CAP)
        want = _s9_read(world, meters, three, eight, questions, S9_LIMIT,
                        S9_BUDGET_CENTS, S9_ROUND_CAP)
        assert isinstance(lost, tuple), (
            "where_it_lost answers a tuple of qids, in the questions' own order, and it "
            "answered %r" % (lost,))
        assert lost == want["lost"], (
            "the questions the checked pipeline paid more for and answered no better are "
            "%r, and where_it_lost named %r" % (want["lost"], lost))
        order = [question["qid"] for question in questions]
        assert [qid for qid in order if qid in lost] == list(lost), (
            "where_it_lost lists the questions in the questions' own order, and it "
            "answered %r" % (lost,))
        assert meter.total_cents() == (want["naive"]["cost_cents"]
                                       + want["checked"]["cost_cents"]), (
            "where_it_lost prices both rows against the meter it was handed — %r cents "
            "against the %r its own pricing costs" % (meter.total_cents(),
                                                      want["naive"]["cost_cents"]
                                                      + want["checked"]["cost_cents"]))
        assert len(meter.charges()) >= 2 * len(questions), (
            "where_it_lost charged the meter only %d times, so it did not price every "
            "question" % (len(meter.charges()),))

    def _s9_rollup(s, world, meters, three, eight):
        """The two rows added up, and the two deltas the checked row's minus the naive's."""
        corpus = world.Corpus.build(7)
        index = three.Index.build(corpus)
        questions = corpus.questions
        meter = meters.Meter()
        rows = s.price(index, corpus, meter, questions, S9_LIMIT, S9_BUDGET_CENTS,
                       S9_ROUND_CAP)
        naive, checked = rows
        summary = s.rollup(rows)
        assert isinstance(summary, dict) and tuple(summary.keys()) == S9_ROLLUP_KEYS, (
            "a rollup is a `%s` record, and it was %r"
            % ("`, `".join(S9_ROLLUP_KEYS), summary))
        cost_cents = naive["cost_cents"] + checked["cost_cents"]
        answered = naive["answered"] + checked["answered"]
        assert summary["cost_cents"] == cost_cents, (
            "a rollup's cost is both rows' costs added up, %r, and it was %r"
            % (cost_cents, summary["cost_cents"]))
        assert summary["answered"] == answered, (
            "a rollup's answered is both rows' answers added up, %r, and it was %r"
            % (answered, summary["answered"]))
        assert answered > 0, (
            "the customer's own questions are all answered by the naive row, so this "
            "rollup divides by %r" % (answered,))
        assert summary["cents_per_answer"] == cost_cents // answered, (
            "one answer cost %r cents over both rows, and the rollup says %r"
            % (cost_cents // answered, summary["cents_per_answer"]))
        assert summary["delta_cents"] == checked["cost_cents"] - naive["cost_cents"], (
            "the cost delta is the checked row's minus the naive row's, %r, and the "
            "rollup says %r" % (checked["cost_cents"] - naive["cost_cents"],
                                summary["delta_cents"]))
        assert summary["delta_answered"] == checked["answered"] - naive["answered"], (
            "the answer delta is the checked row's minus the naive row's, %r, and the "
            "rollup says %r" % (checked["answered"] - naive["answered"],
                                summary["delta_answered"]))
        assert summary["delta_cents"] > 0, (
            "checking costs more than not checking, so the cost delta is positive, and "
            "it was %r" % (summary["delta_cents"],))
        assert summary["delta_answered"] <= 0, (
            "the naive row answers every question, so the checked pipeline cannot have "
            "answered more, and the delta was %r" % (summary["delta_answered"],))
        hand = ({"kind": "naive", "cost_cents": 100, "answered": 10, "hit_bp": 5000},
                {"kind": "checked", "cost_cents": 300, "answered": 12, "hit_bp": 5100})
        counted = s.rollup(hand)
        assert counted["cents_per_answer"] == 400 // 22, (
            "cents per answer is over both rows' answers — 22 of them — and it was %r"
            % (counted["cents_per_answer"],))
        assert counted["delta_cents"] == 200, (
            "the cost delta of the two hand-built rows is 200, and it was %r"
            % (counted["delta_cents"],))
        assert counted["delta_answered"] == 2, (
            "the answer delta of the two hand-built rows is 2, and it was %r"
            % (counted["delta_answered"],))

    def _s9_pair(naive_bp, checked_bp, naive_answered=10, checked_answered=10):
        """Two hand-built rows, so the band's ends and the answered floor can be set."""
        return ({"kind": "naive", "cost_cents": 100, "answered": naive_answered,
                 "hit_bp": naive_bp},
                {"kind": "checked", "cost_cents": 300, "answered": checked_answered,
                 "hit_bp": checked_bp})

    def _s9_worth(s, world, meters, three, eight):
        """The noise band closed at both ends, and the answered floor kept."""
        assert s.worth_it(_s9_pair(5000, 5400)) == "worth-it", (
            "a gain of exactly %d basis points is worth it, and it was %r"
            % (S9_MIN_WORTH_IT_GAIN_BP, s.worth_it(_s9_pair(5000, 5400))))
        assert s.worth_it(_s9_pair(5000, 5399)) == "within-noise", (
            "a gain one basis point under the floor is inside the noise, and it was %r"
            % (s.worth_it(_s9_pair(5000, 5399)),))
        assert s.worth_it(_s9_pair(5000, 5000)) == "within-noise", (
            "a checked row that covered exactly what the naive row did is inside the "
            "noise, and it was %r" % (s.worth_it(_s9_pair(5000, 5000)),))
        assert s.worth_it(_s9_pair(5000, 4601)) == "within-noise", (
            "a loss of 399 basis points is still inside the noise either way, and it "
            "was %r" % (s.worth_it(_s9_pair(5000, 4601)),))
        assert s.worth_it(_s9_pair(5000, 4600)) == "not-worth-it", (
            "a loss of exactly %d basis points is not inside the noise, and it was %r"
            % (S9_MIN_WORTH_IT_GAIN_BP, s.worth_it(_s9_pair(5000, 4600))))
        assert s.worth_it(_s9_pair(5000, 4599)) == "not-worth-it", (
            "a loss past the floor is not worth it, and it was %r"
            % (s.worth_it(_s9_pair(5000, 4599)),))
        assert s.worth_it(_s9_pair(5000, 6000, 10, 9)) == "not-worth-it", (
            "a coverage gain bought by answering fewer questions is not worth it, and "
            "it was %r" % (s.worth_it(_s9_pair(5000, 6000, 10, 9)),))
        assert s.worth_it(_s9_pair(5000, 6000, 10, 11)) == "worth-it", (
            "a gain past the floor with no fewer answers is worth it, and it was %r"
            % (s.worth_it(_s9_pair(5000, 6000, 10, 11)),))
        corpus = world.Corpus.build(7)
        index = three.Index.build(corpus)
        meter = meters.Meter()
        rows = s.price(index, corpus, meter, corpus.questions, S9_LIMIT, S9_BUDGET_CENTS,
                       S9_ROUND_CAP)
        naive, checked = rows
        gain_bp = checked["hit_bp"] - naive["hit_bp"]
        if -S9_MIN_WORTH_IT_GAIN_BP < gain_bp < S9_MIN_WORTH_IT_GAIN_BP:
            want = "within-noise"
        elif (gain_bp >= S9_MIN_WORTH_IT_GAIN_BP
                and checked["answered"] >= naive["answered"]):
            want = "worth-it"
        else:
            want = "not-worth-it"
        assert s.worth_it(rows) == want, (
            "the checked row's %r basis points against the naive row's %r is %r, and "
            "worth_it said %r"
            % (checked["hit_bp"], naive["hit_bp"], want, s.worth_it(rows)))

    def _s9_refuses(s, world, meters, three, eight):
        """Every shape a price cannot be, refused with the call's name and the offender."""
        corpus = world.Corpus.build(7)
        index = three.Index.build(corpus)
        questions = corpus.questions
        meter = meters.Meter()
        rows = s.price(index, corpus, meter, questions, S9_LIMIT, S9_BUDGET_CENTS,
                       S9_ROUND_CAP)
        lines = meter.charges()
        total = meter.total_cents()
        asked = corpus.stats()
        _refuses(ValueError, "a price over questions that are a string",
                 lambda: s.price(index, corpus, meter, "q-01", S9_LIMIT,
                                 S9_BUDGET_CENTS, S9_ROUND_CAP),
                 names=("price", "str"))
        _refuses(ValueError, "a price over a question that is not a record",
                 lambda: s.price(index, corpus, meter, ("q-01",), S9_LIMIT,
                                 S9_BUDGET_CENTS, S9_ROUND_CAP),
                 names=("price", "q-01"))
        _refuses(ValueError, "a price at a limit that is not a count",
                 lambda: s.price(index, corpus, meter, questions, 0, S9_BUDGET_CENTS,
                                 S9_ROUND_CAP),
                 names=("price", "0"))
        _refuses(ValueError, "a price at a limit that is a `bool`",
                 lambda: s.price(index, corpus, meter, questions, True, S9_BUDGET_CENTS,
                                 S9_ROUND_CAP),
                 names=("price", "True"))
        _refuses(ValueError, "a where_it_lost whose questions are a string",
                 lambda: s.where_it_lost(index, corpus, meter, "questions", S9_LIMIT,
                                         S9_BUDGET_CENTS, S9_ROUND_CAP),
                 names=("where_it_lost", "str"))
        _refuses(ValueError, "a where_it_lost at a limit that is not a count",
                 lambda: s.where_it_lost(index, corpus, meter, questions, 0,
                                         S9_BUDGET_CENTS, S9_ROUND_CAP),
                 names=("where_it_lost", "0"))
        _refuses(ValueError, "a rollup of one row",
                 lambda: s.rollup(rows[:1]), names=("rollup", "1"))
        _refuses(ValueError, "a rollup of three rows",
                 lambda: s.rollup(rows + rows[:1]), names=("rollup", "3"))
        _refuses(ValueError, "a rollup of the two rows the wrong way round",
                 lambda: s.rollup((rows[1], rows[0])),
                 names=("rollup", "naive", "checked"))
        _refuses(ValueError, "a rollup of something that is not a row at all",
                 lambda: s.rollup((1, 2)), names=("rollup", "naive", "1"))
        _refuses(ValueError, "a verdict over the two rows the wrong way round",
                 lambda: s.worth_it((rows[1], rows[0])),
                 names=("worth_it", "naive", "checked"))
        assert meter.charges() == lines, (
            "a refused call charged the meter: %r" % (meter.charges()[len(lines):],))
        assert meter.total_cents() == total, (
            "a refused call moved the meter's own total: %r against %r"
            % (meter.total_cents(), total))
        assert corpus.stats() == asked, (
            "a refused call asked the corpus for something: %r" % (corpus.stats(),))

    def _s9_workload(s, world, meters, three, eight):
        """One whole pass of the stage over one corpus, as one tuple."""
        corpus = world.Corpus.build(7)
        index = three.Index.build(corpus)
        questions = corpus.questions
        meter = meters.Meter()
        rows = s.price(index, corpus, meter, questions, S9_LIMIT, S9_BUDGET_CENTS,
                       S9_ROUND_CAP)
        aside = meters.Meter()
        lost = s.where_it_lost(index, corpus, aside, questions, S9_LIMIT,
                               S9_BUDGET_CENTS, S9_ROUND_CAP)
        return (rows, s.rollup(rows), lost, s.worth_it(rows), meter.charges(),
                meter.total_cents(), aside.charges(), aside.total_cents())

    def _s9_twice(s, world, meters, three, eight):
        """Two runs of one workload answer the same thing, ranking, cents and all."""
        one = _s9_workload(s, world, meters, three, eight)
        two = _s9_workload(s, world, meters, three, eight)
        assert one == two, (
            "two runs of one price answered differently, so a run is not a function of "
            "its inputs")

    import corpus as world
    import meter as meters
    import stage_03 as three
    import stage_08 as eight
    import stage_09 as s
    _s9_constants(s, meters)
    _s9_first(s)
    _s9_price(s, world, meters, three, eight)
    _s9_limit(s, world, meters, three, eight)
    _s9_better(s, world, meters, three, eight)
    _s9_empty(s, world, meters, three, eight)
    _s9_budget(s, world, meters, three, eight)
    _s9_lost(s, world, meters, three, eight)
    _s9_rollup(s, world, meters, three, eight)
    _s9_worth(s, world, meters, three, eight)
    _s9_refuses(s, world, meters, three, eight)
    _s9_twice(s, world, meters, three, eight)

# --- stage 10 ----------------------------------------------------------------------
def check_10():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "agentic-retrieval-from-scratch"

    S10_DIAGNOSIS_KEYS = ("fid", "stage", "reason")

    S10_FAILURE_STAGES = ("chunk", "rewrite", "retrieve", "rerank", "ground", "answer",
                          "none")

    S10_EVAL_KEYS = ("answered", "hit_bp", "unsupported_bp", "abstained_correctly",
                     "cost_cents", "verdict")

    S10_EVAL_MIN_SAMPLE = 4

    S10_EVAL_MIN_GAIN_BP = 400

    S10_LIMIT = 5

    S10_BUDGET = 2000

    S10_ROUND_CAP = 2

    def _repo(start=None):
        for candidate_start in (os.environ.get("K1_REPO"), os.environ.get("FDE_REPO"),
                                start, os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "course.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set K1_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked
        against the message: an exception of the right family raised for the wrong
        reason is not the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return refused
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _s10_chunks(seed, doc):
        """Every chunk id the document's own clause index holds, in document order."""
        return tuple("%s:%s" % (doc, number) for number in seed.clause_index(doc))

    def _s10_lies(world, stage5, seed):
        """Eight fabricated rows, one per verdict, each carrying the wrong label.

        A debugger that answers with the label gets every one of them wrong, so what
        the check pins here is the evidence and the exact reason it produces. Which
        question each row answers and which clause it names are read out of the
        corpus as it is now, never written down here: the customer's own facts move,
        and a fixture that names a question as "not ambiguous" goes stale the moment
        the glossary gains a key. Returns the corpus and, by fid, the verdict and the
        reason each row must draw.
        """
        clear = []
        for question in seed.questions:
            if stage5.ambiguous(seed, question) == () and question["expected"]:
                clear.append(question)
        assert len(clear) >= 6, (
            "the check's premise: the corpus holds at least six questions stage 5 finds "
            "nothing to fix in and that expect a clause, and it holds %d" % (len(clear),))
        first, second, missing, ranked, ground, answered = clear[:6]

        def chunks_of(question):
            """The clause ids of the document the question's first expected id is in."""
            return _s10_chunks(seed, question["expected"][0].split(":", 1)[0])

        def elsewhere(question):
            """A clause of that document that is not the question's own expected id."""
            return [chunk for chunk in chunks_of(question)
                    if chunk != question["expected"][0]][0]

        fuzzy = (chunks_of(first)[0],)
        questions = tuple(seed.questions) + (
            {"qid": "q-lie",
             "text": "Does it require deletion on termination, under the MSA?",
             "expected": fuzzy,
             "conversation": ({"speaker": "auditor",
                               "text": "The MSA and the DPA both say something about "
                                       "deletion."},)},)
        dpa = chunks_of(first)
        assert len(dpa) >= 2 and len(chunks_of(second)) >= 3, (
            "the check's premise: the documents the lying rows are built on hold enough "
            "clauses to drop one and two of them and still name a stranger, and they hold "
            "%d and %d" % (len(dpa), len(chunks_of(second))))
        stranger = [chunk for chunk in dpa if chunk not in fuzzy][0]
        rows = (
            ("f-lie-chunk", first["qid"],
             tuple(chunk for chunk in chunks_of(first)
                   if chunk != first["expected"][0]), (), 0, (), False, "ground"),
            ("f-lie-both", second["qid"],
             tuple(chunk for chunk in chunks_of(second)
                   if chunk not in chunks_of(second)[:2]), (), 0, (), False, "rewrite"),
            ("f-lie-rewrite", "q-lie", dpa, (stranger,), 0, (), False, "chunk"),
            ("f-lie-retrieve", missing["qid"], chunks_of(missing), (), 0, (), False,
             "ground"),
            ("f-lie-rerank", ranked["qid"], chunks_of(ranked),
             (elsewhere(ranked), ranked["expected"][0]), 1, (), False, "chunk"),
            ("f-lie-ground", ground["qid"], chunks_of(ground),
             (ground["expected"][0],), 1, (), False, "rerank"),
            ("f-lie-answer", answered["qid"], chunks_of(answered),
             (answered["expected"][0],), 1, (answered["expected"][0],), False, "chunk"),
            ("f-lie-none", seed.questions[-1]["qid"], chunks_of(answered), (), 0, (),
             True, "chunk"),
        )
        failures = tuple({"fid": fid, "qid": qid, "chunks": chunks,
                          "retrieved": retrieved, "kept": kept, "cited": cited,
                          "answer_ok": ok, "stage": stage}
                         for fid, qid, chunks, retrieved, kept, cited, ok, stage in rows)
        plan = {
            "f-lie-chunk": ("chunk", "chunker dropped 1 of %d clauses"
                            % (len(chunks_of(first)),)),
            "f-lie-both": ("chunk", "chunker dropped 2 of %d clauses"
                           % (len(chunks_of(second)),)),
            "f-lie-rewrite": ("rewrite", "ambiguous %s never rewritten, and no expected "
                                         "clause was retrieved"),
            "f-lie-retrieve": ("retrieve", "expected %s was not retrieved"
                               % (missing["expected"][0],)),
            "f-lie-rerank": ("rerank", "expected %s ranked 1 of kept 1"
                             % (ranked["expected"][0],)),
            "f-lie-ground": ("ground", "expected %s was retrieved and not cited"
                             % (ground["expected"][0],)),
            "f-lie-answer": ("answer", "cited %s and answered wrong"
                             % (answered["expected"][0],)),
            "f-lie-none": ("none", "answer was right"),
        }
        return world.Corpus(seed.documents, questions, seed.glossary, failures), plan

    def _s10_clause_text(library, doc, number):
        """The rest of the line `number` opens in the customer's own document text."""
        for line in library.document(doc)["text"].split("\n"):
            if line.split(" ")[0].rstrip() == number:
                return line.split(" ", 1)[1].strip()
        raise AssertionError(
            "the check's premise: document %r opens no clause %r" % (doc, number))

    def _s10_thin(world, seed, goods):
        """The answerable questions asked, and three more that nothing can retrieve."""
        questions = tuple(
            {"qid": "q-good-%d" % (position,),
             "text": _s10_clause_text(seed, doc, number),
             "expected": ("%s:%s" % (doc, number),), "conversation": ()}
            for position, (doc, number) in enumerate(goods))
        questions += (
            {"qid": "q-bad-1", "text": "zebra quark", "expected": ("msa-3:1.1",),
             "conversation": ()},
            {"qid": "q-bad-2", "text": "vulkan fennel", "expected": ("dpa-1:3.1",),
             "conversation": ()},
            {"qid": "q-bad-3", "text": "ptarmigan gantry", "expected": ("sup-1:1.1",),
             "conversation": ()},
        )
        return world.Corpus(seed.documents, questions, seed.glossary, ())

    def _s10_stale(world, seed, text):
        """One question whose only answer is superseded, so abstaining is right."""
        questions = (
            {"qid": "q-stale", "text": text, "expected": ("lic-2:1.2",),
             "conversation": ()},
        )
        return world.Corpus(seed.documents, questions, seed.glossary, ())

    def _s10_nil(world, seed):
        """One question that expects no clause at all, and one failure row for it."""
        questions = ({"qid": "q-nil", "text": "What is nil?", "expected": (),
                      "conversation": ()},)
        failures = ({"fid": "f-nil", "qid": "q-nil", "chunks": (), "retrieved": (),
                     "kept": 0, "cited": (), "answer_ok": False, "stage": "answer"},)
        return world.Corpus(seed.documents, questions, seed.glossary, failures)

    def _s10_reading(meter, stage3, stage8, library, index, questions, limit,
                     budget_cents, round_cap):
        """The check's own reading of the same evaluation, from the loops themselves.

        Answers the six `EVAL_KEYS` fields the contract asks for, measured here over
        a meter of the check's own, so the stage's numbers are not merely believed.
        """
        naive = stage3.measure(index, questions, limit, "hybrid")
        missed = naive["missed"]
        tool = meter.Meter()
        spent = tool.total_cents()
        answered = 0
        right = 0
        expected_ids = 0
        covered = 0
        cited = 0
        unsupported = 0
        for position, question in enumerate(questions):
            held = tool.total_cents()
            loop = stage8.ask(index, library, tool, question, position, limit,
                              held + budget_cents, round_cap)
            answer = loop["answer"]
            if answer is None:
                continue
            if answer["abstained"]:
                if question["qid"] in missed:
                    right += 1
                continue
            answered += 1
            expected = question["expected"]
            cites = answer["citations"]
            expected_ids += len(expected)
            cited += len(cites)
            covered += len([chunk for chunk in expected if chunk in cites])
            unsupported += len([chunk for chunk in cites if chunk not in expected])
        hit_bp = covered * 10000 // expected_ids if expected_ids else 0
        gain_bp = hit_bp - naive["hit_bp"]
        if answered >= S10_EVAL_MIN_SAMPLE and gain_bp >= S10_EVAL_MIN_GAIN_BP:
            verdict = "beat-baseline"
        elif answered < S10_EVAL_MIN_SAMPLE or gain_bp < 0:
            verdict = "worse"
        else:
            verdict = "no-better"
        return {"answered": answered,
                "hit_bp": hit_bp,
                "unsupported_bp": unsupported * 10000 // cited if cited else 0,
                "abstained_correctly": right,
                "cost_cents": tool.total_cents() - spent,
                "verdict": verdict}

    def _s10_constants(s):
        assert tuple(s.DIAGNOSIS_KEYS) == S10_DIAGNOSIS_KEYS, (
            "a diagnosis is (fid, stage, reason) in that order, and the stage spells it %r"
            % (s.DIAGNOSIS_KEYS,))
        assert tuple(s.FAILURE_STAGES) == S10_FAILURE_STAGES, (
            "the failure vocabulary is %r in that order — `rewrite` between `chunk` and "
            "`retrieve`, `none` last — and the stage spells it %r"
            % (S10_FAILURE_STAGES, s.FAILURE_STAGES))
        assert tuple(s.EVAL_KEYS) == S10_EVAL_KEYS, (
            "the checker's report is %r in that order, and the stage spells it %r"
            % (S10_EVAL_KEYS, s.EVAL_KEYS))
        assert s.EVAL_MIN_SAMPLE == S10_EVAL_MIN_SAMPLE, (
            "a verdict stands on %d answers, and the stage asks for %r"
            % (S10_EVAL_MIN_SAMPLE, s.EVAL_MIN_SAMPLE))
        assert s.EVAL_MIN_GAIN_BP == S10_EVAL_MIN_GAIN_BP, (
            "the gain bound is %d basis points, and the stage says %r"
            % (S10_EVAL_MIN_GAIN_BP, s.EVAL_MIN_GAIN_BP))

    def _s10_diagnose(s, library):
        """The customer's own rows, blamed exactly as the customer blamed them."""
        before = library.stats()
        rows = []
        for failure in library.failures:
            got = s.diagnose(library, failure)
            assert tuple(got) == S10_DIAGNOSIS_KEYS, (
                "a diagnosis is (fid, stage, reason), and %r came back for %r"
                % (tuple(got), failure["fid"]))
            assert got["fid"] == failure["fid"], (
                "the diagnosis of %r names %r" % (failure["fid"], got["fid"]))
            assert got["stage"] == failure["stage"], (
                "the debugger blamed %r for %r and the customer blamed %r, so the tree does "
                "not reproduce the label from the evidence"
                % (got["stage"], failure["fid"], failure["stage"]))
            assert isinstance(got["reason"], str) and got["reason"], (
                "the diagnosis of %r gives the reason %r" % (failure["fid"], got["reason"]))
            rows.append(got)
        after = library.stats()
        needed = len([failure for failure in library.failures
                      if not failure["answer_ok"]])
        assert after["lookups"] - before["lookups"] == needed, (
            "a row whose answer was right still had the library walked for it: %d lookups "
            "for %d rows that had evidence to decide"
            % (after["lookups"] - before["lookups"], needed))
        assert after["documents"] == 8 and after["clauses"] == sum(
            len(library.clause_index(document["doc"])) for document in library.documents), (
            "the library's own recount changed under the diagnosis: %r" % (after,))
        return rows

    def _s10_evidence(s, world, stage5, library):
        """Eight rows whose own labels lie, pinning every branch and its reason."""
        lied, plan = _s10_lies(world, stage5, library)
        lying = {}
        for question in lied.questions:
            lying[question["qid"]] = question
        kinds = tuple(fix["kind"] for fix in stage5.ambiguous(lied, lying["q-lie"]))
        assert len(kinds) >= 2, (
            "the check's premise: the rewrite fixture's question is ambiguous in more than "
            "one way, so the kinds have to be joined, and stage 5's own `ambiguous` found "
            "%r" % (kinds,))
        for failure in lied.failures:
            want = plan[failure["fid"]]
            assert failure["stage"] != want[0], (
                "the check's own fixture %r carries the same label as its evidence, so it "
                "cannot tell a debugger that reads the label from one that reads the tree"
                % (failure["fid"],))
            got = s.diagnose(lied, failure)
            assert got["stage"] == want[0], (
                "the evidence of %r implies %r and the debugger answered %r"
                % (failure["fid"], want[0], got["stage"]))
            reason = want[1] % (",".join(kinds),) if "%s" in want[1] else want[1]
            assert got["reason"] == reason, (
                "the reason for %r is %r, and %r came back"
                % (failure["fid"], reason, got["reason"]))
        stripped = _s10_without(lied.failures[0], "stage")
        got = s.diagnose(lied, stripped)
        assert got["stage"] == plan[lied.failures[0]["fid"]][0], (
            "the debugger decides without the customer's label, so a row without that field "
            "at all is judged on its evidence too, and the answer was %r" % (got["stage"],))

    def _s10_distribution(s):
        rows = ({"fid": "f-b", "stage": "retrieve", "reason": "r"},
                {"fid": "f-a", "stage": "retrieve", "reason": "r"},
                {"fid": "f-c", "stage": "ground", "reason": "r"},
                {"fid": "f-d", "stage": "none", "reason": "r"})
        got = s.distribution(rows)
        assert tuple(got) == ("counts", "by_stage", "worst"), (
            "the distribution is (counts, by_stage, worst) in that order, and it is %r"
            % (tuple(got),))
        assert tuple(got["counts"]) == S10_FAILURE_STAGES, (
            "the counts hold every stage of the vocabulary in its order, and they are %r"
            % (tuple(got["counts"]),))
        assert got["counts"] == {"chunk": 0, "rewrite": 0, "retrieve": 2, "rerank": 0,
                                 "ground": 1, "answer": 0, "none": 1}, (
            "two rows blamed retrieval, one grounding and one nothing, and the counts are %r"
            % (got["counts"],))
        assert tuple(got["by_stage"]) == S10_FAILURE_STAGES, (
            "the fids are held by every stage of the vocabulary in its order, and the keys "
            "are %r" % (tuple(got["by_stage"]),))
        assert got["by_stage"]["retrieve"] == ("f-a", "f-b"), (
            "the fids of a stage are sorted, and retrieval's are %r"
            % (got["by_stage"]["retrieve"],))
        assert got["by_stage"]["chunk"] == (), (
            "a stage with no failures holds no fids, and chunk holds %r"
            % (got["by_stage"]["chunk"],))
        assert got["worst"] == "retrieve", (
            "retrieval failed most often, and the worst stage is %r" % (got["worst"],))
        tied = ({"fid": "f-e", "stage": "none", "reason": "r"},
                {"fid": "f-f", "stage": "none", "reason": "r"},
                {"fid": "f-g", "stage": "none", "reason": "r"},
                {"fid": "f-h", "stage": "answer", "reason": "r"},
                {"fid": "f-i", "stage": "chunk", "reason": "r"})
        got = s.distribution(tied)
        assert got["counts"]["none"] == 3, (
            "three rows answered correctly and the counts say %r" % (got["counts"],))
        assert got["worst"] == "chunk", (
            "`none` is never the failing stage and a tie is broken by the vocabulary's own "
            "order, so one chunk failure, one answer failure and three correct rows blame "
            "%r" % (got["worst"],))
        empty = s.distribution(())
        assert empty["counts"] == {stage: 0 for stage in S10_FAILURE_STAGES}, (
            "no diagnoses is every stage at zero, and the counts are %r"
            % (empty["counts"],))
        assert empty["by_stage"] == {stage: () for stage in S10_FAILURE_STAGES}, (
            "no diagnoses is every stage empty, and the fids are %r" % (empty["by_stage"],))
        assert empty["worst"] == "chunk", (
            "with no failures at all the total tie is settled by the vocabulary's own "
            "order, and the worst stage is %r" % (empty["worst"],))

    def _s10_agreement(s, library):
        rows = tuple(s.diagnose(library, failure) for failure in library.failures)
        got = s.agreement(rows, library)
        assert tuple(got) == ("agree", "disagree", "bp"), (
            "the agreement is (agree, disagree, bp) in that order, and it is %r"
            % (tuple(got),))
        assert (got["agree"], got["disagree"], got["bp"]) == (len(rows), (), 10000), (
            "the customer's own labels confirm all %d diagnoses, and the agreement is %r"
            % (len(rows), got))
        other = "answer" if rows[0]["stage"] != "answer" else "chunk"
        flipped = tuple([dict(rows[0], stage=other)] + list(rows[1:]))
        got = s.agreement(flipped, library)
        assert got["agree"] == len(rows) - 1, (
            "one diagnosis of %d was re-blamed and the agreement counts %r"
            % (len(rows), got["agree"]))
        assert got["disagree"] == (rows[0]["fid"],), (
            "one diagnosis of %d was re-blamed and the disagreements are %r"
            % (len(rows), got["disagree"]))
        assert got["bp"] == (len(rows) - 1) * 10000 // len(rows), (
            "the share is agree over the diagnoses given, and it is %r" % (got["bp"],))
        fewer = s.agreement(rows[:5], library)
        assert (fewer["agree"], fewer["bp"]) == (5, 10000), (
            "five diagnoses held against the customer's record are all confirmed and the "
            "share is over the diagnoses given rather than over the twelve failures: %r"
            % (fewer,))
        pair = (dict(rows[-1], stage=other), dict(rows[0], stage=other))
        got = s.agreement(pair, library)
        assert got["disagree"] == tuple(sorted((rows[0]["fid"], rows[-1]["fid"]))), (
            "the disagreements are a sorted tuple of fids, and in the order the diagnoses "
            "arrived they would be %r" % (got["disagree"],))
        assert (got["agree"], got["bp"]) == (0, 0), (
            "neither of the two re-blamed diagnoses matches the customer's own label, and "
            "the agreement is %r" % (got,))

    def _s10_without(record, key):
        """A copy of `record` with one field missing — the shape a row must refuse."""
        copy = dict(record)
        del copy[key]
        return copy

    def _s10_changed(record, key, value):
        """A copy of `record` with one field replaced."""
        return dict(record, **{key: value})

    def _s10_eval(s, world, meter, stage3, stage8, library, index):
        """The checker's report against the loops the check runs for itself."""
        questions = library.questions
        fresh = meter.Meter()
        fresh.charge("embed", 1, 0)
        charged = fresh.total_cents()
        got = s.eval_checker(index, library, questions, fresh, S10_LIMIT, S10_BUDGET,
                             S10_ROUND_CAP)
        assert tuple(got) == S10_EVAL_KEYS, (
            "the checker's report is %r in that order, and it is %r"
            % (S10_EVAL_KEYS, tuple(got)))
        want = _s10_reading(meter, stage3, stage8, library, index, questions, S10_LIMIT,
                            S10_BUDGET, S10_ROUND_CAP)
        for key in S10_EVAL_KEYS:
            assert got[key] == want[key], (
                "the checker reported %r for %r and the loops stage 8 ran say %r"
                % (got[key], key, want[key]))
        assert got["cost_cents"] == fresh.total_cents() - charged, (
            "the cost of the evaluation is the meter's own delta: the meter already held %d "
            "cents, it holds %d now, and the report says %r"
            % (charged, fresh.total_cents(), got["cost_cents"]))
        assert (got["cost_cents"] == fresh.stats()["cents"] - charged
                and got["cost_cents"] > 0 and fresh.stats()["charges"] > 1), (
            "an evaluation that charges nothing asked the customer nothing: %r"
            % (fresh.stats(),))
        assert library.stats()["documents"] == 8, (
            "the library's own recount of the corpus under test is %r" % (library.stats(),))

        goods = (("msa-3", "3.2"), ("msa-3", "4.1"), ("msa-3", "8.1"), ("dpa-1", "6.1"))
        thin = _s10_thin(world, library, goods)
        thin_index = stage3.Index.build(thin)
        naive = stage3.measure(thin_index, thin.questions, S10_LIMIT, "hybrid")
        want = _s10_reading(meter, stage3, stage8, thin, thin_index, thin.questions,
                            S10_LIMIT, S10_BUDGET, S10_ROUND_CAP)
        assert (want["answered"] == S10_EVAL_MIN_SAMPLE
                and want["hit_bp"] - naive["hit_bp"] >= S10_EVAL_MIN_GAIN_BP), (
            "the check's premise: %d answerable questions beside three nothing can retrieve "
            "make exactly the sample floor of %d, and the coverage is far above the "
            "baseline's %d: %r"
            % (len(goods), S10_EVAL_MIN_SAMPLE, naive["hit_bp"], want))
        assert want["abstained_correctly"] >= 1, (
            "the check's premise: the naive retrieval cannot answer the three questions "
            "nothing can retrieve, so their abstentions are right ones: %r" % (want,))
        got = s.eval_checker(thin_index, thin, thin.questions, meter.Meter(), S10_LIMIT,
                             S10_BUDGET, S10_ROUND_CAP)
        for key in S10_EVAL_KEYS:
            assert got[key] == want[key], (
                "on the thin corpus the checker reported %r for %r and the loops say %r"
                % (got[key], key, want[key]))
        assert got["verdict"] == "beat-baseline", (
            "the floor is met exactly and the coverage is far above the baseline, so the "
            "verdict is `beat-baseline`, and it is %r" % (got["verdict"],))

        fewer = _s10_thin(world, library, goods[:S10_EVAL_MIN_SAMPLE - 1])
        fewer_index = stage3.Index.build(fewer)
        got = s.eval_checker(fewer_index, fewer, fewer.questions, meter.Meter(), S10_LIMIT,
                             S10_BUDGET, S10_ROUND_CAP)
        assert got["verdict"] == "worse", (
            "one answer short of the floor is `worse` however good the coverage is, and it "
            "is %r" % (got["verdict"],))

        stale = _s10_stale(world, library, _s10_clause_text(library, "lic-2", "1.2"))
        stale_index = stage3.Index.build(stale)
        naive = stage3.measure(stale_index, stale.questions, S10_LIMIT, "hybrid")
        assert naive["missed"] == (), (
            "the check's premise: the naive retrieval does find the superseded clause of "
            "the question, and it reports %r as missed" % (naive["missed"],))
        got = s.eval_checker(stale_index, stale, stale.questions, meter.Meter(), S10_LIMIT,
                             S10_BUDGET, S10_ROUND_CAP)
        assert got["answered"] == 0, (
            "the question's only clause is superseded, so the answer is an abstention, and "
            "the report counts %r answers" % (got["answered"],))
        assert got["abstained_correctly"] == 0, (
            "the pipeline abstained on a question whose expected clause the naive retrieval "
            "does find, so that abstention is not one of the right ones, and the report "
            "counts %r" % (got["abstained_correctly"],))
        assert got["verdict"] == "worse", (
            "with no answers at all the verdict is `worse`, and it is %r" % (got["verdict"],))

        price = meter.Meter()
        stage8.ask(index, library, price, questions[0], 0, S10_LIMIT, 10 ** 9, 0)
        one_round = price.total_cents()
        assert 0 < one_round < S10_BUDGET, (
            "the check's premise: one round of the checked loop costs the meter %d cents, "
            "well under the budget a run is given" % (one_round,))
        want = _s10_reading(meter, stage3, stage8, library, index, questions, S10_LIMIT,
                            one_round, S10_ROUND_CAP)
        assert want["cost_cents"] == one_round * len(questions), (
            "the check's premise: a budget of exactly one round's price buys exactly one "
            "round for every question, so the run costs %d cents and the reading says %r"
            % (one_round * len(questions), want["cost_cents"]))
        assert want["answered"] > 0, (
            "the check's premise: one round per question answers something, and the reading "
            "says %r" % (want,))
        got = s.eval_checker(index, library, questions, meter.Meter(), S10_LIMIT, one_round,
                             S10_ROUND_CAP)
        for key in S10_EVAL_KEYS:
            assert got[key] == want[key], (
                "with a budget of one round's price the checker reported %r for %r and the "
                "loops say %r" % (got[key], key, want[key]))

        want = _s10_reading(meter, stage3, stage8, library, index, questions, S10_LIMIT, 0,
                            S10_ROUND_CAP)
        got = s.eval_checker(index, library, questions, meter.Meter(), S10_LIMIT, 0,
                             S10_ROUND_CAP)
        assert tuple(got) == S10_EVAL_KEYS, (
            "an evaluation that can afford no round still answers the report's own keys in "
            "order, and it answered %r" % (tuple(got),))
        for key in S10_EVAL_KEYS:
            assert got[key] == want[key], (
                "with a budget of no cents at all the checker reported %r for %r and the "
                "loops say %r" % (got[key], key, want[key]))
        assert (got["answered"], got["abstained_correctly"], got["cost_cents"]) == (0, 0, 0), (
            "no question could afford a single round, so nothing was answered, no abstention "
            "was a right one and nothing was charged, and the report says %r" % (got,))
        assert got["verdict"] == "worse", (
            "an evaluation that answered nothing is `worse` whatever the coverage says, and "
            "it is %r" % (got["verdict"],))

    def _s10_refusals(s, world, meter, stage5, library, index):
        """Every guard, on both sides of every boundary, each naming its offender."""
        first = library.failures[0]
        lie, _plan = _s10_lies(world, stage5, library)
        nil = _s10_nil(world, library)
        before = library.stats()
        _refuses(ValueError, "a failure row that is not a mapping",
                 lambda: s.diagnose(library, "f-01"), names=("str",))
        _refuses(ValueError, "a failure row with no kept count",
                 lambda: s.diagnose(library, _s10_without(first, "kept")), names=("kept",))
        _refuses(ValueError, "a kept count that is a bool",
                 lambda: s.diagnose(library, _s10_changed(first, "kept", True)),
                 names=("kept",))
        _refuses(ValueError, "an answer_ok that is not a bool",
                 lambda: s.diagnose(library, _s10_changed(first, "answer_ok", 1)),
                 names=("f-01",))
        _refuses(ValueError, "a failure row for a question the corpus does not hold",
                 lambda: s.diagnose(library, _s10_changed(first, "qid", "q-99")),
                 names=("q-99",))
        _refuses(ValueError, "a failure row holding a chunk of another document",
                 lambda: s.diagnose(library,
                                    _s10_changed(first, "chunks", ("dpa-1:1.1",))),
                 names=("dpa-1:1.1", "msa-3"))
        _refuses(ValueError, "a failure row whose chunks hold a whole number",
                 lambda: s.diagnose(library, _s10_changed(first, "chunks", (1,))),
                 names=("1",))
        _refuses(ValueError, "a failure row whose chunks are not a tuple of names",
                 lambda: s.diagnose(library,
                                    _s10_changed(first, "chunks", "msa-3:4.2(a)")),
                 names=("msa-3:4.2(a)",))
        _refuses(ValueError, "a failure row for a question that expects no clause",
                 lambda: s.diagnose(nil, nil.failures[0]), names=("q-nil",))
        _refuses(ValueError, "a corpus that is not the customer's library",
                 lambda: s.diagnose("corpus", first), names=("str",))
        assert library.stats() == before, (
            "a refused diagnosis asked the library anyway: %r" % (library.stats(),))
        dumped = ({"fid": "f-01", "stage": "chunk", "reason": "r"},)
        _refuses(ValueError, "diagnoses that are not a tuple of rows",
                 lambda: s.distribution("rows"), names=("rows",))
        _refuses(ValueError, "a diagnosis row that is not a mapping",
                 lambda: s.distribution(("f-01",)), names=("str",))
        _refuses(ValueError, "a diagnosis row with no reason",
                 lambda: s.distribution((_s10_without(dumped[0], "reason"),)),
                 names=("reason",))
        _refuses(ValueError, "a diagnosis blaming a stage outside the vocabulary",
                 lambda: s.distribution((_s10_changed(dumped[0], "stage", "chunking"),)),
                 names=("chunking", "f-01"))
        _refuses(ValueError, "a diagnosis whose stage is not a string",
                 lambda: s.distribution((_s10_changed(dumped[0], "stage", 3),)),
                 names=("3",))
        _refuses(ValueError, "a diagnosis whose fid is not a string",
                 lambda: s.distribution((_s10_changed(dumped[0], "fid", 7),)),
                 names=("7",))
        _refuses(ValueError, "a diagnosis whose reason is not a string",
                 lambda: s.distribution((_s10_changed(dumped[0], "reason", 7),)),
                 names=("7",))
        _refuses(ValueError, "a diagnosis for a failure the corpus does not hold",
                 lambda: s.agreement((_s10_changed(dumped[0], "fid", "f-99"),), library),
                 names=("f-99",))
        _refuses(ValueError, "a corpus that is not the customer's library",
                 lambda: s.agreement(dumped, "corpus"), names=("str",))
        _refuses(ValueError, "an index that is not an Index",
                 lambda: s.eval_checker("index", library, library.questions, meter.Meter(),
                                        S10_LIMIT, S10_BUDGET, S10_ROUND_CAP),
                 names=("str",))
        _refuses(ValueError, "a corpus that is not the customer's library",
                 lambda: s.eval_checker(index, "corpus", library.questions, meter.Meter(),
                                        S10_LIMIT, S10_BUDGET, S10_ROUND_CAP),
                 names=("str",))
        _refuses(ValueError, "a meter that is not the customer's meter",
                 lambda: s.eval_checker(index, library, library.questions, "meter",
                                        S10_LIMIT, S10_BUDGET, S10_ROUND_CAP),
                 names=("str",))
        _refuses(ValueError, "questions that are not a tuple of rows",
                 lambda: s.eval_checker(index, library, "questions", meter.Meter(),
                                        S10_LIMIT, S10_BUDGET, S10_ROUND_CAP),
                 names=("questions",))
        tool = meter.Meter()
        _refuses(ValueError, "a limit of no hits at all",
                 lambda: s.eval_checker(index, library, library.questions, tool, 0,
                                        S10_BUDGET, S10_ROUND_CAP), names=("0",))
        _refuses(ValueError, "a limit that is not a whole number",
                 lambda: s.eval_checker(index, library, library.questions, tool, "5",
                                        S10_BUDGET, S10_ROUND_CAP), names=("5",))
        _refuses(ValueError, "a budget of negative cents",
                 lambda: s.eval_checker(index, library, library.questions, tool, S10_LIMIT,
                                        -1, S10_ROUND_CAP), names=("-1",))
        _refuses(ValueError, "a budget that is not a whole number",
                 lambda: s.eval_checker(index, library, library.questions, tool, S10_LIMIT,
                                        "600", S10_ROUND_CAP), names=("600",))
        _refuses(ValueError, "a round cap of negative rounds",
                 lambda: s.eval_checker(index, library, library.questions, tool, S10_LIMIT,
                                        S10_BUDGET, -1), names=("-1",))
        _refuses(ValueError, "a round cap that is not a whole number",
                 lambda: s.eval_checker(index, library, library.questions, tool, S10_LIMIT,
                                        S10_BUDGET, "2"), names=("2",))
        _refuses(ValueError, "a question the corpus does not hold",
                 lambda: s.eval_checker(index, library, ({"qid": "q-99"},), tool, S10_LIMIT,
                                        S10_BUDGET, S10_ROUND_CAP), names=("q-99",))
        assert tool.total_cents() == 0 and tool.stats()["charges"] == 0, (
            "a refused evaluation charged the customer's meter: %r" % (tool.stats(),))
        assert library.stats() == before, (
            "a refused evaluation left a line in the library's own log: %r"
            % (library.stats(),))
        assert lie.failures and nil.failures, (
            "the crafted fixtures are the check's own and they must hold their rows")

    def _s10_workload(s, world, meter, stage3, stage8, library, index):
        """One whole pass of the stage over the fixtures built here, as one value."""
        rows = tuple(s.diagnose(library, failure) for failure in library.failures)
        return (rows, s.distribution(rows), s.agreement(rows, library),
                s.eval_checker(index, library, library.questions, meter.Meter(), S10_LIMIT,
                               S10_BUDGET, S10_ROUND_CAP))

    def _s10_twice(s, world, meter, stage3, stage8, library, index):
        one = _s10_workload(s, world, meter, stage3, stage8, library, index)
        two = _s10_workload(s, world, meter, stage3, stage8, library, index)
        assert one == two, (
            "two runs of one workload answered differently, so a run is not a function of "
            "its inputs")

    import corpus as world
    import meter
    import stage_03
    import stage_05
    import stage_08
    import stage_10 as s

    library = world.Corpus.build(7)
    index = stage_03.Index.build(library)
    _s10_constants(s)
    _s10_diagnose(s, library)
    _s10_evidence(s, world, stage_05, library)
    _s10_distribution(s)
    _s10_agreement(s, library)
    _s10_eval(s, world, meter, stage_03, stage_08, library, index)
    _s10_refusals(s, world, meter, stage_05, library, index)
    _s10_twice(s, world, meter, stage_03, stage_08, library, index)

# --- the manifest. One entry per stage, in the order a reader meets them.

STAGES = [
    stage(
        1,
        file="stage_01.py",
        title="The clause, the cross-reference and the chunk that cites itself",
        tags=["chunking", "citations", "contracts"],
        action="Write `CHUNK_KEYS`, `PARSE_PROBLEMS`, `chunk`, `problems_of`, "
               "`chunk_id`, `resolve`, `definitions`, `refs_of` and `outline` in "
               "stage_01.py.",
        predict="Where a clause ends when the next line is a continuation rather "
                "than a new clause, and what the chunker does with a clause number "
                "the document uses twice.",
        check=check_1,
    ),
    stage(
        2,
        file="stage_02.py",
        title="Ten million documents, and the index that is a decision",
        tags=["index", "capacity", "planning"],
        action="Write `LAYOUTS`, `PLAN_PROBLEMS`, `weigh`, `bytes_of`, `scan_of`, "
               "`plan` and `explain` in stage_02.py.",
        predict="Which layout a memory budget buys once sharding pays for a "
                "dictionary per shard, and what a plan says when nothing fits.",
        check=check_2,
    ),
    stage(
        3,
        file="stage_03.py",
        title="Two scorers, and the fusion that has to beat both",
        tags=["bm25", "embeddings", "fusion"],
        action="Write `HIT_KEYS`, `MEASURE_KEYS`, `Index`, `bm25`, `dense`, `fuse`, "
               "`search`, `measure` and `pick` in stage_03.py.",
        predict="What an inverse document frequency does to a fixed-point BM25 "
                "score, and which of the three modes the customer's own labelled "
                "questions prefer.",
        check=check_3,
    ),
    stage(
        4,
        file="stage_04.py",
        title="The reranker that must earn its place",
        tags=["reranking", "measurement", "noise"],
        action="Write `RERANK_KEYS`, `COMPARE_KEYS`, `rerank`, `compare` and `keep` "
               "in stage_04.py.",
        predict="How much of a coverage gain is real signal and how much is noise, "
                "and what the stage answers when the gain is inside the bound.",
        check=check_4,
    ),
    stage(
        5,
        file="stage_05.py",
        title="The ambiguous question, rewritten and recorded",
        tags=["rewriting", "ambiguity", "decomposition"],
        action="Write `REWRITE_KEYS`, `REWRITE_KINDS`, `PRONOUNS`, `REFERENT_STOP`, "
               "`ambiguous`, `rewrite` and `decompose` in stage_05.py.",
        predict="Where a pronoun's referent comes from when the question does not "
                "name it, and what a two-hop question has to be turned into.",
        check=check_5,
    ),
    stage(
        6,
        file="stage_06.py",
        title="The critique of what came back",
        tags=["critique", "staleness", "conflicts"],
        action="Write `CRITIQUE_KEYS`, `CRITIQUE_VERDICTS`, `VERDICT_ORDER`, "
               "`critique`, `survivors` and `by_verdict` in stage_06.py.",
        predict="Which of a chunk's four possible faults wins when more than one is "
                "true of it, and what a conflict is measured against.",
        check=check_6,
    ),
    stage(
        7,
        file="stage_07.py",
        title="Grounded or abstain, and never a claim without a citation",
        tags=["grounding", "abstention", "citations"],
        action="Write `CLAIM_KEYS`, `ANSWER_KEYS`, `ABSTENTIONS`, `CITATION_PROBLEMS`, "
               "`grounding_bp`, `answer` and `check_citations` in stage_07.py.",
        predict="What an answer is made of when the pipeline may quote but may not "
                "invent, and which abstention reason is decided first.",
        check=check_7,
    ),
    stage(
        8,
        file="stage_08.py",
        title="The loop that must terminate, priced every round",
        tags=["loops", "budgets", "termination"],
        action="Write `ROUND_KEYS`, `LOOP_KEYS`, `STOPS`, `ask` and `rounds_of` in "
               "stage_08.py.",
        predict="When the budget is checked, what stops a loop that keeps rewriting "
                "to the same query, and whose number a round's cost is.",
        check=check_8,
    ),
    stage(
        9,
        file="stage_09.py",
        title="What the checking cost, against the naive answer",
        tags=["cost", "baseline", "roi"],
        action="Write `BASELINE_KEYS`, `ROLLUP_KEYS`, `price`, `rollup`, "
               "`where_it_lost` and `worth_it` in stage_09.py.",
        predict="What the naive pipeline's answered count is by construction, and "
                "what a rollup says when nothing was answered at all.",
        check=check_9,
    ),
    stage(
        10,
        file="stage_10.py",
        title="Which stage failed, and whether the checker beat the baseline",
        tags=["debugging", "labelled-failures", "eval"],
        action="Write `DIAGNOSIS_KEYS`, `FAILURE_STAGES`, `EVAL_KEYS`, `diagnose`, "
               "`distribution`, `agreement` and `eval_checker` in stage_10.py.",
        predict="Which piece of evidence separates a chunking failure from a "
                "retrieval one, and what makes an abstention the right answer.",
        check=check_10,
    ),
]
