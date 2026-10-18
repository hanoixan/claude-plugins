"""Tests for interview.py.

Each test works in a temporary skel/ folder with a small weights file for "Ann",
and runs the script as the agent would.

Run from the repository root:

    python3 -m unittest discover -s plugins/skel/tests
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

SKILL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "skills", "skel")
SCRIPT = os.path.join(SKILL, "scripts", "interview.py")
CHECK = os.path.join(SKILL, "scripts", "skel_check.py")
EXAMPLE = os.path.join(SKILL, "assets", "examples", "undo-system", "skel")

_spec = importlib.util.spec_from_file_location("interview", SCRIPT)
iv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(iv)

WEIGHTS = """# skel interview weights

## C1 reliability
meaning: keeps working when something fails.
tags: reliability
rating: 10 · by: Ann · 2026-10-01

## C2 effort
meaning: work to build.
tags: impl-effort
rating: 1 · by: Ann · 2026-10-01

## C3 privacy
meaning: data stays with its owner.
tags: privacy
rating: 7 · by: Ann · 2026-10-01
"""

CHEAP = ("Cheap (Recommended)", "reliability 2", "impl-effort 2")
STURDY = ("Sturdy", "impl-effort 2", "reliability 2")
PRIVATE = ("Private", "impl-effort 1", "privacy 2")
PLAIN = ("Plain", "privacy 1", "impl-effort 1")
ASKED = "2026-10-02 10:00:00 +0000"

LOG_RECORD = """# skel interviews

## Q1
<tracer> Where is undo history kept?
header: History · round: 1 · select: single · asked: 2026-10-02 10:00:00 +0000 · by: Ann
- <sel> **Cheap (Recommended)**: about cheap.
    concern: a worry about cheap.
    raises: reliability 2
    addresses: impl-effort 2
- * **Sturdy**: about sturdy.
    concern: a worry about sturdy.
    raises: impl-effort 2
    addresses: reliability 2
prediction: Sturdy · score 18 · gap 36 · model: stated
concern-only: Sturdy
axis: C2 effort vs C1 reliability
"""


def question(n, text="Which way?", choices=(CHEAP, STURDY), select="single", annotated=True):
    lines = [f"## Q{n}", text, f"header: H{n} · select: {select}"]
    for label, raises, addresses in choices:
        word = label.split()[0].lower()
        lines.append(f"- **{label}**: about {word}.")
        if annotated:
            lines += [f"    concern: a worry about {word}.", f"    raises: {raises}", f"    addresses: {addresses}"]
    return "\n".join(lines) + "\n"


def draft(*questions):
    return iv.DRAFT_TITLE + "\n\n" + "\n".join(questions)


def records(text, title=None):
    problems = iv.Problems()
    recs = iv.parse_records("x.md", text.splitlines(keepends=True), title or iv.DRAFT_TITLE, problems)
    return recs, problems


class Case(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="skel-interview-")
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.skel = os.path.join(self.dir, "skel")
        os.mkdir(self.skel)
        self.write(iv.WEIGHTS, WEIGHTS)

    def path(self, name):
        return os.path.join(self.skel, name)

    def write(self, name, text):
        with open(self.path(name), "w", encoding="utf-8", newline="") as fh:
            fh.write(text)

    def read(self, name):
        with open(self.path(name), encoding="utf-8", newline="") as fh:
            return fh.read()

    def cli(self, command, *args, ok=True):
        result = subprocess.run([sys.executable, SCRIPT, command, self.skel, *args],
                                capture_output=True, text=True, cwd=self.dir)
        if ok:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def round(self, *questions, answers, by="Ann"):
        self.write(iv.DRAFT, draft(*questions))
        self.cli("predict", "--by", by)
        return self.cli("record", "--by", by, "--answers", answers, "--asked", ASKED)

    def state(self):
        return iv.load(self.skel)


class Parsing(Case):
    def test_a_full_log_record_parses(self):
        recs, problems = records(LOG_RECORD, iv.LOG_TITLE)
        iv.validate_records("x.md", recs, problems, log=True)
        self.assertEqual(problems.errors, [])
        rec = recs[0]
        self.assertEqual(rec.marks, ["tracer"])
        self.assertEqual(rec.question, "Where is undo history kept?")
        self.assertEqual(rec.by, "Ann")
        self.assertEqual([c.sel for c in rec.choices], [True, False])
        self.assertEqual([c.predicted for c in rec.choices], [False, True])
        self.assertEqual(rec.choices[0].raises, [("reliability", 2)])
        self.assertTrue(rec.choices[0].recommended)
        self.assertEqual(rec.fields["axis"], "C2 effort vs C1 reliability")

    def test_parse_accepts_a_good_log(self):
        self.write(iv.LOG, LOG_RECORD)
        result = self.cli("parse")
        self.assertIn("1 record", result.stdout)

    def test_marks_in_the_wrong_order_are_an_error(self):
        self.write(iv.LOG, LOG_RECORD.replace("- <sel> **Cheap", "- * <sel> **Cheap"))
        result = self.cli("parse", ok=False)
        self.assertIn("`<sel>` then `*`", result.stdout + result.stderr)

    def test_errors_name_the_file_and_line(self):
        self.write(iv.LOG, LOG_RECORD.replace("- <sel> **Cheap", "- * <sel> **Cheap"))
        result = self.cli("parse", ok=False)
        self.assertIn(".interviews.md:6:", result.stdout + result.stderr)

    def test_a_choice_that_raises_nothing_is_an_error(self):
        self.write(iv.LOG, LOG_RECORD.replace("    raises: reliability 2", "    raises: none"))
        result = self.cli("parse", ok=False)
        self.assertIn("raises at least one concern", result.stdout + result.stderr)

    def test_a_partly_annotated_choice_is_an_error(self):
        self.write(iv.LOG, LOG_RECORD.replace("    concern: a worry about cheap.\n", ""))
        result = self.cli("parse", ok=False)
        self.assertIn("all of concern:, raises: and addresses:", result.stdout + result.stderr)

    def test_an_unannotated_log_choice_is_a_warning(self):
        text = LOG_RECORD.replace("    concern: a worry about cheap.\n    raises: reliability 2\n"
                                  "    addresses: impl-effort 2\n", "")
        self.write(iv.LOG, text)
        result = self.cli("parse")
        self.assertIn("not annotated", result.stdout)

    def test_records_are_numbered_in_order(self):
        self.write(iv.LOG, LOG_RECORD.replace("## Q1", "## Q2"))
        result = self.cli("parse", ok=False)
        self.assertIn("expected Q1", result.stdout + result.stderr)

    def test_probe_goes_before_tracer(self):
        self.write(iv.LOG, LOG_RECORD.replace("<tracer> Where", "<tracer> <probe> Where"))
        result = self.cli("parse", ok=False)
        self.assertIn("`<probe>` then `<tracer>`", result.stdout + result.stderr)

    def test_a_single_choice_answer_has_one_sel(self):
        self.write(iv.LOG, LOG_RECORD.replace("- * **Sturdy", "- <sel> * **Sturdy"))
        result = self.cli("parse", ok=False)
        self.assertIn("one <sel>", result.stdout + result.stderr)

    def test_an_answered_question_needs_a_sel(self):
        self.write(iv.LOG, LOG_RECORD.replace("- <sel> **Cheap", "- **Cheap"))
        result = self.cli("parse", ok=False)
        self.assertIn("marks its choice with <sel>", result.stdout + result.stderr)

    def test_a_declined_question_has_no_sel(self):
        self.write(iv.LOG, LOG_RECORD.replace("prediction:", "answer: none (declined)\nprediction:"))
        result = self.cli("parse", ok=False)
        self.assertIn("declined question has no <sel>", result.stdout + result.stderr)

    def test_blank_lines_inside_a_record_are_allowed(self):
        self.write(iv.LOG, LOG_RECORD.replace("- * **Sturdy", "\n- * **Sturdy"))
        self.cli("parse")

    def test_a_tag_in_two_concerns_is_an_error(self):
        self.write(iv.WEIGHTS, WEIGHTS.replace("tags: impl-effort", "tags: impl-effort, reliability"))
        result = self.cli("parse", ok=False)
        self.assertIn("`reliability` is in C1 and C2", result.stdout + result.stderr)

    def test_a_rating_out_of_range_is_an_error(self):
        self.write(iv.WEIGHTS, WEIGHTS.replace("rating: 10 ·", "rating: 11 ·"))
        result = self.cli("parse", ok=False)
        self.assertIn("rating:", result.stdout + result.stderr)

    def test_the_latest_rating_counts(self):
        self.write(iv.WEIGHTS, WEIGHTS.replace("rating: 1 · by: Ann · 2026-10-01",
                                               "rating: 1 · by: Ann · 2026-10-01\nrating: 4 · by: Ann · 2026-10-05"))
        self.assertEqual(iv.stated(self.state().concerns, "Ann"), {1: 10.0, 2: 4.0, 3: 7.0})

    def test_the_seed_has_16_concerns_and_18_tags(self):
        problems = iv.Problems()
        concerns = iv.parse_weights("seed", iv.seed_lines(), problems)
        self.assertEqual(problems.errors, [])
        self.assertEqual(len(concerns), 16)
        self.assertEqual(sum(len(c.tags) for c in concerns), 18)

    def test_rebuild_of_an_unchanged_file_is_byte_identical(self):
        text = LOG_RECORD.replace("\n", "\r\n")
        lines = text.splitlines(keepends=True)
        recs, _ = records(text, iv.LOG_TITLE)
        self.assertEqual(iv.rebuild(lines, recs), text)


class Concerns(Case):
    def test_concerns_lists_unmapped_tags_and_unrated_concerns(self):
        self.write(iv.DRAFT, draft(question(1, choices=(CHEAP, ("Offline", "offline 1", "reliability 1")))))
        result = self.cli("concerns", "--by", "Bob")
        self.assertIn("offline", result.stdout)
        self.assertIn("C1 reliability", result.stdout)
        self.assertNotIn("C3 privacy", result.stdout)

    def test_concerns_json(self):
        self.write(iv.DRAFT, draft(question(1)))
        data = json.loads(self.cli("concerns", "--by", "Bob", "--json").stdout)
        self.assertEqual(data["unmapped"], [])
        self.assertEqual([c["id"] for c in data["unrated"]], [1, 2])

    def test_nothing_to_do_says_so(self):
        self.write(iv.DRAFT, draft(question(1)))
        self.assertIn("Nothing to map or rate", self.cli("concerns", "--by", "Ann").stdout)


class TagAndRate(Case):
    def test_tag_adds_a_tag_to_a_concern(self):
        self.cli("tag", "offline", "C1")
        self.assertIn("tags: reliability, offline\n", self.read(iv.WEIGHTS))

    def test_tag_new_appends_a_concern_with_the_next_id(self):
        self.cli("tag", "NEW:offline", "--new", "offline use", "works without a network.")
        self.assertTrue(self.read(iv.WEIGHTS).endswith(
            "\n## C4 offline use\nmeaning: works without a network.\ntags: NEW:offline\n"))

    def test_a_tag_maps_to_one_concern(self):
        result = self.cli("tag", "reliability", "C2", ok=False)
        self.assertIn("already belongs to C1 reliability", result.stderr)

    def test_tag_needs_a_concern_or_new(self):
        self.cli("tag", "offline", ok=False)

    def test_tag_creates_the_weights_from_the_seed(self):
        os.remove(self.path(iv.WEIGHTS))
        self.cli("tag", "NEW:offline", "--new", "offline use", "works without a network.")
        text = self.read(iv.WEIGHTS)
        self.assertTrue(text.startswith(iv.WEIGHTS_TITLE + "\n\n## C1 security\n"))
        self.assertIn("## C17 offline use\n", text)

    def test_rate_appends_a_rating(self):
        self.cli("rate", "C2=4", "C3=5.5", "--by", "Ann", "--date", "2026-10-05")
        text = self.read(iv.WEIGHTS)
        self.assertIn("rating: 1 · by: Ann · 2026-10-01\nrating: 4 · by: Ann · 2026-10-05\n", text)
        self.assertIn("rating: 5.5 · by: Ann · 2026-10-05\n", text)
        self.assertEqual(iv.stated(self.state().concerns, "Ann"), {1: 10.0, 2: 4.0, 3: 5.5})

    def test_rate_refuses_a_value_out_of_range(self):
        before = self.read(iv.WEIGHTS)
        self.cli("rate", "C2=4", "C3=12", "--by", "Ann", ok=False)
        self.assertEqual(self.read(iv.WEIGHTS), before)

    def test_rate_refuses_an_unknown_concern(self):
        self.cli("rate", "C9=4", "--by", "Ann", ok=False)

    def test_crlf_weights_stay_crlf(self):
        self.write(iv.WEIGHTS, WEIGHTS.replace("\n", "\r\n"))
        self.cli("rate", "C2=4", "--by", "Ann", "--date", "2026-10-05")
        self.cli("tag", "offline", "C1")
        text = self.read(iv.WEIGHTS)
        self.assertNotIn("\n", text.replace("\r\n", ""))
        self.assertIn("tags: reliability, offline\r\n", text)

    def test_by_defaults_to_the_git_user(self):
        subprocess.run(["git", "init", "-q", self.dir], check=True)
        subprocess.run(["git", "-C", self.dir, "config", "user.name", "Ann"], check=True)
        self.cli("rate", "C2=3", "--date", "2026-10-05")
        self.assertIn("rating: 3 · by: Ann · 2026-10-05", self.read(iv.WEIGHTS))


class Coexistence(unittest.TestCase):
    def test_check_ignores_the_interview_files(self):
        work = tempfile.mkdtemp(prefix="skel-interview-tree-")
        self.addCleanup(shutil.rmtree, work, ignore_errors=True)
        skel = os.path.join(work, "skel")
        shutil.copytree(EXAMPLE, skel)
        for name, text in ((iv.LOG, LOG_RECORD), (iv.WEIGHTS, WEIGHTS), (iv.DRAFT, draft(question(1)))):
            with open(os.path.join(skel, name), "w", encoding="utf-8") as fh:
                fh.write(text)
        result = subprocess.run([sys.executable, CHECK, "check", skel], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
