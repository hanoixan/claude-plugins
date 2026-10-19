"""Tests for question-refiner's hooks. Run: python3 -m unittest discover -s plugins/question-refiner/tests"""
import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from test_refiner import LOG_RECORD, WEIGHTS, SCRIPT, draft, iv as rf, question

HOOKS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hooks")
GATE = os.path.join(HOOKS, "gate.py")
DETECT = os.path.join(HOOKS, "detect.py")
RULE = os.path.join(HOOKS, "rule.sh")


class Hook(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="question-refiner-hooks-")
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.store = os.path.join(self.dir, rf.STORE)
        os.mkdir(self.store)
        self.write(rf.WEIGHTS, WEIGHTS)

    def write(self, name, text, folder=None):
        path = os.path.join(folder or self.store, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)

    def refiner(self, command, *args):
        subprocess.run([sys.executable, SCRIPT, command, "--dir", self.store, *args], check=True,
                       capture_output=True, text=True)

    def run_hook(self, script, payload):
        result = subprocess.run([sys.executable, script], input=payload, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)["hookSpecificOutput"] if result.stdout.strip() else None

    def gate(self, *questions, stdin=None):
        payload = stdin if stdin is not None else json.dumps({
            "hook_event_name": "PreToolUse", "tool_name": "AskUserQuestion", "cwd": self.dir,
            "tool_input": {"questions": [{"question": q, "header": "H", "multiSelect": False,
                                          "options": [{"label": "A", "description": "a"},
                                                      {"label": "B", "description": "b"}]} for q in questions]}})
        return self.run_hook(GATE, payload)

    def detect(self):
        out = self.run_hook(DETECT, json.dumps({"hook_event_name": "SessionStart", "source": "startup",
                                                "cwd": self.dir}))
        return out["additionalContext"] if out else None

    def predicted(self):
        self.write(rf.DRAFT, draft(question(1)))
        self.refiner("predict", "--by", "Ann")

    def legacy(self):
        skel = os.path.join(self.dir, "skel")
        self.write(rf.LEGACY_LOG, LOG_RECORD.replace(rf.LOG_TITLE, "# skel interviews"), skel)
        self.write(rf.LEGACY_WEIGHTS, WEIGHTS.replace(rf.WEIGHTS_TITLE, "# skel interview weights"), skel)
        return skel

    def test_a_predicted_question_passes(self):
        self.predicted()
        self.assertIsNone(self.gate("Which way?"))

    def test_a_recent_exempt_question_passes(self):
        self.refiner("exempt", "--question", "Merge?", "--reason", "a menu", "--by", "Ann")
        self.assertIsNone(self.gate("Merge?"))

    def test_an_old_exempt_question_is_refused(self):
        old = (datetime.datetime.now().astimezone() - datetime.timedelta(minutes=20)).strftime(rf.STAMP_FORMAT)
        self.refiner("exempt", "--question", "Merge?", "--reason", "a menu", "--by", "Ann", "--asked", old)
        self.assertEqual(self.gate("Merge?")["permissionDecision"], "deny")

    def test_only_the_failing_questions_are_named(self):
        self.predicted()
        reason = self.gate("Which way?", "Which way?!")["permissionDecisionReason"]
        self.assertIn("- Which way?!", reason)
        self.assertNotIn("- Which way?\n", reason)
        self.assertIn("predict", reason)
        self.assertIn("exempt", reason)

    def test_bad_input_is_let_through(self):
        out = self.gate(stdin="not json")
        self.assertNotIn("permissionDecision", out)
        self.assertIn("could not check", out["additionalContext"])

    def test_a_store_that_does_not_parse_is_let_through(self):
        self.write(rf.LOG, "# wrong title\n")
        out = self.gate("Anything?")
        self.assertNotIn("permissionDecision", out)
        self.assertIn("could not check", out["additionalContext"])

    def test_a_round_that_does_not_parse_is_refused(self):
        self.predicted()
        with open(os.path.join(self.store, rf.DRAFT), encoding="utf-8") as fh:
            text = fh.read()
        self.write(rf.DRAFT, "".join(l for l in text.splitlines(keepends=True) if not l.startswith("header:")))
        out = self.gate("Which way?")
        self.assertEqual(out["permissionDecision"], "deny")
        self.assertIn("round.md", out["permissionDecisionReason"])

    def test_the_refusal_mentions_marks(self):
        self.predicted()
        self.assertIn("without its `<probe>` mark", self.gate("<probe> Which way?")["permissionDecisionReason"])

    def test_detect_says_a_fresh_start_needs_the_user(self):
        self.legacy()
        text = self.detect()
        self.assertIn("--fresh only when the user chooses a fresh start", text)
        self.assertIn("migrating data deferred", text)

    def test_detect_names_unmigrated_data(self):
        self.legacy()
        text = self.detect()
        self.assertIn("`skel/` (1 record, ratings for 1 person)", text)
        self.assertIn("import", text)
        self.assertIn("migrating data", text)

    def test_detect_is_silent_once_the_store_has_a_log(self):
        self.legacy()
        self.write(rf.LOG, LOG_RECORD)
        self.assertIsNone(self.detect())

    def test_detect_is_silent_once_the_data_is_moved(self):
        self.write(rf.MOVED, "# Moved\n", self.legacy())
        self.assertIsNone(self.detect())

    @unittest.skipUnless(shutil.which("bash") and shutil.which("jq"), "needs bash and jq")
    def test_the_rule_is_added_every_turn(self):
        result = subprocess.run(["bash", RULE], input="{}", capture_output=True, text=True,
                                env={**os.environ, "CLAUDE_PLUGIN_DATA": self.dir})
        context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("goes through a question-refiner round", context)

    def test_hooks_json_wires_the_three_events(self):
        with open(os.path.join(HOOKS, "hooks.json"), encoding="utf-8") as fh:
            hooks = json.load(fh)["hooks"]
        self.assertEqual(hooks["PreToolUse"][0]["matcher"], "AskUserQuestion")
        self.assertEqual(hooks["SessionStart"][0]["matcher"], "startup|clear")
        self.assertIn("rule.sh", hooks["UserPromptSubmit"][0]["hooks"][0]["command"])


if __name__ == "__main__":
    unittest.main()
