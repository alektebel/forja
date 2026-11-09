const test = require("node:test");
const assert = require("node:assert/strict");
const learning = require("./learning.js");
const lessons = require("../../aws-from-scratch/lessons.json");

test("the four S3 pilot stages have one checkable concept and distinct transfer case", () => {
  for (const id of [9, 10, 11, 12]) {
    const record = lessons[id - 1].learning;
    assert.ok(record.check_case && record.failure_focus);
    for (const question of [record.concept, record.transfer]) {
      assert.ok(question.prompt);
      assert.equal(question.options.length, question.feedback.length);
      assert.ok(question.correct >= 0 && question.correct < question.options.length);
    }
    assert.notEqual(record.concept.prompt, record.transfer.prompt);
  }
});

test("the helper names the unfinished target and avoids an unnecessary probe", () => {
  const source = "    def put_object(self):\n        raise NotImplementedError\n    def get_object(self):\n        raise NotImplementedError";
  const advice = learning.runAdvice({}, "S3.put_object / S3.get_object",
    { status: "TODO" }, source, []);
  assert.match(advice.message, /put_object/);
  assert.equal(advice.probe, false);
});

test("a first failure shows the focused case; an unchanged rerun asks for an edit", () => {
  const metadata = { check_case: "The checker reads a/b.txt.", failure_focus: "Inspect the key." };
  const source = "def get_object():\n    return None";
  const first = learning.runAdvice(metadata, "get_object", { status: "FAIL" }, source, []);
  assert.equal(first.probe, false);
  assert.match(first.message, /a\/b.txt/);
  const second = learning.runAdvice(metadata, "get_object", { status: "FAIL" }, source,
    [{ status: "FAIL", sourceHash: learning.fingerprint(source) }]);
  assert.equal(second.probe, false);
  assert.match(second.message, /same code/);
});

test("the run coach follows the actual failing check across edits", () => {
  const metadata = { failure_focus: "Inspect the full key." };
  const firstSource = "def get_object():\n    return None";
  const secondSource = "def get_object():\n    return b'wrong'";
  const first = { status: "FAIL", check: { line: 103,
    expression: 'assert store.get_object("b", "a/b.txt").body == b"hello"' } };
  const firstAdvice = learning.runAdvice(metadata, "get_object", first, firstSource, []);
  assert.match(firstAdvice.message, /get_object\("b", "a\/b.txt"\)/);
  const history = [{ status: "FAIL", checkId: 103, sourceHash: learning.fingerprint(firstSource) }];
  const repeat = learning.runAdvice(metadata, "get_object", first, secondSource, history);
  assert.match(repeat.message, /same check still fails/);
  assert.equal(repeat.probe, true);
  const next = learning.runAdvice(metadata, "get_object", { status: "FAIL", check: {
    line: 105, expression: 'assert exc.code == "NoSuchKey"' } }, secondSource, history);
  assert.match(next.message, /different check/);
  assert.match(next.message, /NoSuchKey/);
  const passed = learning.runAdvice(metadata, "get_object", { status: "PASS" }, secondSource, history);
  assert.match(passed.message, /latest change passed/);
});

test("a lookup error receives the stage's specific focus", () => {
  const advice = learning.runAdvice({ check_case: "Read absent.", failure_focus: "Distinguish missing from empty." },
    "S3.get_object", { status: "ERROR", detail: "s3.py:100: KeyError: 'absent'" }, "", []);
  assert.match(advice.message, /missing from empty/);
  assert.equal(advice.probe, false);
});

test("recall waits for later progress or a day, and records an answer separately", () => {
  const now = 2 * 24 * 60 * 60 * 1000;
  const pilot = { 9: { transfer: { prompt: "New case", options: ["A", "B"], correct: 0,
    feedback: ["Yes", "No"] } } };
  const events = [{ kind: "run", stage: 9, status: "PASS", ts: now - 1000 }];
  assert.equal(learning.duePractice(events, [9], pilot, 9, now), null);
  assert.equal(learning.duePractice(events, [9, 10], pilot, 11, now), 9);
  assert.equal(learning.duePractice(events, [9], pilot, 9, now + 24 * 60 * 60 * 1000), 9);
  assert.equal(learning.duePractice([...events, { kind: "practice", stage: 9, correct: true, ts: now }],
    [9, 10], pilot, 11, now), null);
  const wrong = learning.answer(pilot[9].transfer, 1);
  assert.deepEqual(wrong, { correct: false, feedback: "No" });
});

test("event storage is bounded and malformed local data does not break the workspace", () => {
  let value = "broken";
  const storage = { getItem: () => value, setItem: (_, next) => { value = next; } };
  assert.deepEqual(learning.read(storage), []);
  for (let i = 0; i < 405; i++) learning.append(storage, { kind: "run", stage: i });
  assert.equal(learning.read(storage).length, 400);
  assert.equal(learning.read(storage)[0].stage, 5);
});
