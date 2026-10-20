"""Tests for refiner.py.

Each test works in a temporary .question-refiner/ store with a small weights file for "Ann",
and runs the script as the agent would.

Run from the repository root:

    python3 -m unittest discover -s plugins/question-refiner/tests
"""
import datetime
import importlib.util
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

SKILL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "skills", "question-refiner")
SCRIPT = os.path.join(SKILL, "scripts", "refiner.py")

_spec = importlib.util.spec_from_file_location("refiner", SCRIPT)
iv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(iv)

WEIGHTS = """# question-refiner weights

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

LOG_RECORD = """# question-refiner interviews

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


LEGACY_LOG = LOG_RECORD.replace(iv.LOG_TITLE, "# skel interviews")
LEGACY_WEIGHTS = WEIGHTS.replace(iv.WEIGHTS_TITLE, "# skel interview weights")

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
        self.dir = tempfile.mkdtemp(prefix="question-refiner-")
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.store = os.path.join(self.dir, iv.STORE)
        os.mkdir(self.store)
        self.write(iv.WEIGHTS, WEIGHTS)

    def path(self, name):
        return os.path.join(self.store, name)

    def write(self, name, text):
        with open(self.path(name), "w", encoding="utf-8", newline="") as fh:
            fh.write(text)

    def read(self, name):
        with open(self.path(name), encoding="utf-8", newline="") as fh:
            return fh.read()

    def cli(self, command, *args, ok=True):
        result = subprocess.run([sys.executable, SCRIPT, command, "--dir", self.store, *args],
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
        return iv.load(self.store)


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
        self.assertIn(f"{iv.LOG}:6:", result.stdout + result.stderr)

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

    def test_tag_without_weights_says_to_choose_domains(self):
        os.remove(self.path(iv.WEIGHTS))
        result = self.cli("tag", "NEW:offline", "--new", "offline use", "works without a network.", ok=False)
        self.assertIn("domains add", result.stderr)

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


ANN = {1: 10.0, 2: 1.0, 3: 7.0}


class Scoring(unittest.TestCase):
    def tags(self, weights=WEIGHTS):
        return iv.tag_map(iv.parse_weights("w", weights.splitlines(keepends=True), iv.Problems()))

    def vectors(self, rec, weights=WEIGHTS):
        tags = self.tags(weights)
        return [iv.vector(c, tags) for c in rec.choices]

    def test_score_adds_addresses_and_subtracts_raises(self):
        rec = records(draft(question(1)))[0][0]
        self.assertEqual([iv.score(v, ANN) for v in self.vectors(rec)], [-18.0, 18.0])

    def test_tags_of_one_concern_add_up(self):
        weights = WEIGHTS.replace("tags: reliability", "tags: reliability, uptime")
        rec = records(draft(question(1, choices=(("A", "reliability 1, uptime 2", "impl-effort 1"), STURDY))))[0][0]
        self.assertEqual(self.vectors(rec, weights)[0], {1: -3, 2: 1})

    def test_the_top_score_is_predicted_with_its_lead(self):
        rec = records(draft(question(1)))[0][0]
        picked, scores, gap = iv.choose(rec, self.vectors(rec), ANN)
        self.assertEqual((picked, gap), ([1], 36.0))

    def test_a_tie_goes_to_the_recommended_choice(self):
        rec = records(draft(question(1, choices=(STURDY, CHEAP))))[0][0]
        picked, _, _ = iv.choose(rec, self.vectors(rec), {1: 5.0, 2: 5.0})
        self.assertEqual(picked, [1])

    def test_a_tie_without_a_recommendation_goes_to_the_first_choice(self):
        rec = records(draft(question(1, choices=(STURDY, ("Quick", "reliability 2", "impl-effort 2")))))[0][0]
        picked, _, _ = iv.choose(rec, self.vectors(rec), {1: 5.0, 2: 5.0})
        self.assertEqual(picked, [0])

    def test_multi_select_predicts_every_positive_choice(self):
        rec = records(draft(question(1, choices=(CHEAP, STURDY, PRIVATE), select="multi")))[0][0]
        picked, scores, gap = iv.choose(rec, self.vectors(rec), ANN)
        self.assertEqual((picked, gap), ([1, 2], 13.0))

    def test_multi_select_with_nothing_positive_predicts_the_best(self):
        rec = records(draft(question(1, choices=(CHEAP, ("Worse", "reliability 3", "impl-effort 1")),
                                     select="multi")))[0][0]
        picked, _, _ = iv.choose(rec, self.vectors(rec), ANN)
        self.assertEqual(picked, [0])

    def test_the_axis_names_the_concern_gained_and_the_one_lost(self):
        rec = records(draft(question(1)))[0][0]
        cheap, sturdy = self.vectors(rec)
        self.assertEqual(iv.axis(cheap, sturdy), (2, 1))
        self.assertIsNone(iv.axis(cheap, cheap))


class Predict(Case):
    def test_predict_marks_the_top_choice_and_writes_the_prediction(self):
        self.write(iv.DRAFT, draft(question(1)))
        result = self.cli("predict", "--by", "Ann")
        text = self.read(iv.DRAFT)
        self.assertIn("- * **Sturdy**: about sturdy.\n", text)
        self.assertIn("- **Cheap (Recommended)**: about cheap.\n", text)
        self.assertIn("prediction: Sturdy · score 18 · gap 36 · p 97% · model: stated\n", text)
        self.assertIn("concern-only: Sturdy\n", text)
        self.assertIn("model: stated", result.stdout)

    def test_predict_refuses_an_unannotated_choice(self):
        self.write(iv.DRAFT, draft(question(1, annotated=False)))
        result = self.cli("predict", "--by", "Ann", ok=False)
        self.assertIn("not annotated", result.stderr)

    def test_predict_refuses_an_unmapped_tag(self):
        self.write(iv.DRAFT, draft(question(1, choices=(CHEAP, ("Offline", "offline 1", "reliability 1")))))
        result = self.cli("predict", "--by", "Ann", ok=False)
        self.assertIn("refiner.py tag", result.stderr)

    def test_predict_refuses_a_concern_the_person_has_not_rated(self):
        self.write(iv.DRAFT, draft(question(1)))
        result = self.cli("predict", "--by", "Bob", ok=False)
        self.assertIn("C1 reliability is not rated by Bob", result.stderr)

    def test_a_failed_predict_writes_nothing(self):
        text = draft(question(1), question(2, annotated=False))
        self.write(iv.DRAFT, text)
        self.cli("predict", "--by", "Ann", ok=False)
        self.assertEqual(self.read(iv.DRAFT), text)

    def test_predicting_twice_gives_the_same_round(self):
        self.write(iv.DRAFT, draft(question(1), question(2, choices=(CHEAP, STURDY, PRIVATE))))
        self.cli("predict", "--by", "Ann")
        once = self.read(iv.DRAFT)
        self.cli("predict", "--by", "Ann")
        self.assertEqual(self.read(iv.DRAFT), once)

    def test_predict_keeps_crlf_and_untouched_lines(self):
        self.write(iv.DRAFT, draft(question(1)).replace("\n", "\r\n"))
        self.cli("predict", "--by", "Ann")
        text = self.read(iv.DRAFT)
        self.assertNotIn("\n", text.replace("\r\n", ""))
        self.assertIn("header: H1 · select: single · by: Ann\r\n", text)
        self.assertIn("    concern: a worry about cheap.\r\n", text)


class Record(Case):
    def test_record_appends_the_round_and_deletes_the_draft(self):
        self.round(question(1), answers="Q1=2")
        text = self.read(iv.LOG)
        self.assertTrue(text.startswith(iv.LOG_TITLE + "\n\n## Q1\nWhich way?\n"))
        self.assertIn("header: H1 · round: 1 · select: single · asked: 2026-10-02 10:00:00 +0000 · by: Ann\n", text)
        self.assertIn("- <sel> * **Sturdy**: about sturdy.\n", text)
        self.assertNotIn("<tracer>", text)
        self.assertFalse(os.path.exists(self.path(iv.DRAFT)))
        self.cli("parse")

    def test_a_dissenting_answer_is_a_tracer_with_its_axis(self):
        result = self.round(question(1), answers="Q1=1")
        text = self.read(iv.LOG)
        self.assertIn("## Q1\n<tracer> Which way?\n", text)
        self.assertIn("- <sel> **Cheap (Recommended)**", text)
        self.assertIn("axis: C2 effort vs C1 reliability\n", text)
        self.assertIn("tracer", result.stdout)

    def test_other_is_always_a_tracer(self):
        self.write(iv.DRAFT, draft(question(1)))
        self.cli("predict", "--by", "Ann")
        with open(self.path(iv.DRAFT), "a", encoding="utf-8") as fh:
            fh.write("- **Other**: keep the last ten steps.\n"
                     "    concern: ten steps may be too few.\n"
                     "    raises: reliability 1\n"
                     "    addresses: impl-effort 1\n")
        self.cli("record", "--by", "Ann", "--answers", "Q1=Other", "--asked", ASKED)
        text = self.read(iv.LOG)
        self.assertIn("<tracer> Which way?", text)
        self.assertIn("- <sel> **Other**: keep the last ten steps.\n    concern:", text)
        self.assertIn("axis: C2 effort vs C1 reliability\n", text)

    def test_record_refuses_other_without_its_choice(self):
        self.write(iv.DRAFT, draft(question(1)))
        self.cli("predict", "--by", "Ann")
        result = self.cli("record", "--by", "Ann", "--answers", "Q1=Other", "--asked", ASKED, ok=False)
        self.assertIn("- **Other**: <text>", result.stderr)

    def test_record_refuses_bad_answers(self):
        self.write(iv.DRAFT, draft(question(1), question(2)))
        self.cli("predict", "--by", "Ann")
        before = self.read(iv.DRAFT)
        for answers, message in (("Q1=2", "Q2 has no answer"), ("Q1=2, Q2=3", "out of range"),
                                 ("Q1=1+2, Q2=1", "single-choice"), ("Q1=1, Q2=1, Q3=1", "Q3 is not in the round"),
                                 ("Q1=x, Q2=1", "Q1=x")):
            result = self.cli("record", "--by", "Ann", "--answers", answers, "--asked", ASKED, ok=False)
            self.assertIn(message, result.stderr)
        self.assertEqual(self.read(iv.DRAFT), before)
        self.assertFalse(os.path.exists(self.path(iv.LOG)))

    def test_record_refuses_a_round_that_was_not_predicted(self):
        self.write(iv.DRAFT, draft(question(1)))
        result = self.cli("record", "--by", "Ann", "--answers", "Q1=1", "--asked", ASKED, ok=False)
        self.assertIn("run `refiner.py predict` first", result.stderr)

    def test_none_records_a_declined_question(self):
        self.round(question(1), answers="Q1=none")
        text = self.read(iv.LOG)
        self.assertIn("answer: none (declined)\n", text)
        self.assertNotIn("<sel>", text)
        self.assertNotIn("<tracer>", text)

    def test_numbers_and_rounds_continue_the_log(self):
        self.round(question(1), answers="Q1=2")
        self.round(question(1, text="Again?"), question(2, text="And?"), answers="Q1=2, Q2=1")
        text = self.read(iv.LOG)
        self.assertIn("## Q2\nAgain?\nheader: H1 · round: 2 ·", text)
        self.assertIn("## Q3\n<tracer> And?\nheader: H2 · round: 2 ·", text)
        self.cli("parse")

    def test_the_round_summary_leaves_declined_questions_out(self):
        result = self.round(question(1), question(2), answers="Q1=2, Q2=none")
        self.assertIn("round 1: 1 of 1 predictions hit", result.stdout)

    def test_the_round_summary_says_which_predictions_hit(self):
        result = self.round(question(1), question(2), answers="Q1=2, Q2=1")
        self.assertIn("Q1: Sturdy (predicted)\n", result.stdout)
        self.assertIn("Q2: Cheap (Recommended) (predicted: Sturdy), tracer:", result.stdout)

    def test_multi_select_answers_join_with_plus(self):
        self.round(question(1, choices=(CHEAP, STURDY, PRIVATE), select="multi"), answers="Q1=1+2")
        text = self.read(iv.LOG)
        self.assertIn("- <sel> **Cheap", text)
        self.assertIn("- <sel> * **Sturdy", text)
        self.assertNotIn("<tracer>", text)

    def test_a_new_rating_does_not_change_a_recorded_round(self):
        self.round(question(1), answers="Q1=1")
        before = self.read(iv.LOG)
        self.cli("rate", "C1=0", "--by", "Ann", "--date", "2026-10-05")
        self.assertEqual(self.read(iv.LOG), before)


class Fitting(Case):
    def dissent_rounds(self, n):
        for _ in range(n):
            self.round(question(1), answers="Q1=1")

    def test_no_fit_below_five_tracers(self):
        self.dissent_rounds(4)
        self.write(iv.DRAFT, draft(question(1)))
        self.assertIn("model: stated", self.cli("predict", "--by", "Ann").stdout)
        self.assertIn("4 tracers", self.cli("fit", "--by", "Ann").stdout)

    def test_five_tracers_fit_the_weights(self):
        self.dissent_rounds(5)
        self.write(iv.DRAFT, draft(question(1)))
        self.cli("predict", "--by", "Ann")
        self.assertIn("model: fitted+rec", self.read(iv.DRAFT))

    def test_the_fit_moves_toward_the_dissent(self):
        self.dissent_rounds(5)
        w, w_rec, model, _ = iv.weights_for(self.state(), "Ann")
        self.assertEqual(model, "fitted+rec")
        self.assertLess(w[1] - w[2], 9.0)
        self.assertGreater(w_rec, 0.0)

    def test_the_fit_is_deterministic(self):
        self.dissent_rounds(5)
        self.assertEqual(iv.weights_for(self.state(), "Ann"), iv.weights_for(self.state(), "Ann"))

    def test_weights_stay_within_their_bounds(self):
        self.dissent_rounds(6)
        w, w_rec, _, _ = iv.weights_for(self.state(), "Ann")
        self.assertTrue(all(0.0 <= x <= 10.0 for x in w.values()))
        self.assertTrue(-10.0 <= w_rec <= 10.0)

    def test_multi_select_and_declined_are_left_out_of_fitting(self):
        self.round(question(1, choices=(CHEAP, STURDY, PRIVATE), select="multi"), answers="Q1=1+2")
        self.round(question(1), answers="Q1=none")
        self.round(question(1), answers="Q1=1")
        state = self.state()
        self.assertEqual(len(iv.fit_data(state.log, iv.tag_map(state.concerns), "Ann")), 1)

    def test_other_people_are_left_out(self):
        text = WEIGHTS
        for ann in ("rating: 10 · by: Ann · 2026-10-01\n", "rating: 1 · by: Ann · 2026-10-01\n",
                    "rating: 7 · by: Ann · 2026-10-01\n"):
            text = text.replace(ann, ann + "rating: 5 · by: Bob · 2026-10-01\n")
        self.write(iv.WEIGHTS, text)
        self.round(question(1), answers="Q1=1", by="Bob")
        state = self.state()
        self.assertEqual(iv.fit_data(state.log, iv.tag_map(state.concerns), "Ann"), [])

    def test_overfit_warning(self):
        self.assertEqual(iv.overfit({1: 0.0, 2: 5.0}, {1: 10.0, 2: 1.0}, [], "Ann"), [1])
        self.assertEqual(iv.overfit({1: 8.0}, {1: 10.0}, [], "Ann"), [])

    def test_fit_reports_stated_and_fitted_weights(self):
        self.dissent_rounds(5)
        data = json.loads(self.cli("fit", "--by", "Ann", "--json").stdout)
        self.assertEqual(data["model"], "fitted+rec")
        self.assertEqual({c["id"] for c in data["concerns"]}, {1, 2, 3})
        self.assertIn("w_rec", data)

    def test_a_long_history_fits_in_reasonable_time(self):
        body = []
        for n in range(1, 201):
            body.append(LOG_RECORD.split("\n", 2)[2].replace("## Q1", f"## Q{n}").replace("round: 1", f"round: {n}"))
        self.write(iv.LOG, iv.LOG_TITLE + "\n\n" + "\n".join(body))
        start = time.monotonic()
        iv.weights_for(self.state(), "Ann")
        self.assertLess(time.monotonic() - start, 10.0)


class Probes(Case):
    def test_a_question_on_a_dissent_axis_is_a_probe(self):
        self.round(question(1), answers="Q1=1")
        self.write(iv.DRAFT, draft(question(1, text="Again?", choices=(STURDY, CHEAP))))
        self.cli("predict", "--by", "Ann")
        text = self.read(iv.DRAFT)
        self.assertIn("## Q1\n<probe> Again?\n", text)
        self.assertIn("probes: C1 reliability vs C2 effort\n", text)

    def test_a_question_off_the_dissent_axes_is_not_a_probe(self):
        self.round(question(1), answers="Q1=1")
        self.write(iv.DRAFT, draft(question(1, choices=(PRIVATE, PLAIN))))
        self.cli("predict", "--by", "Ann")
        self.assertNotIn("<probe>", self.read(iv.DRAFT))

    def test_a_probe_is_kept_in_the_log(self):
        self.round(question(1), answers="Q1=1")
        self.round(question(1, text="Again?"), answers="Q1=1")
        self.assertIn("## Q2\n<probe> <tracer> Again?\n", self.read(iv.LOG))
        self.cli("parse")


class Hits(Case):
    def test_hits_counts_shown_and_stated(self):
        self.round(question(1), answers="Q1=2")
        self.round(question(1), answers="Q1=1")
        out = self.cli("hits", "--by", "Ann").stdout
        self.assertIn("Shown predictions: 1 of 2", out)
        self.assertIn("Stated ratings only: 1 of 2", out)

    def test_other_counts_as_a_miss(self):
        self.write(iv.DRAFT, draft(question(1)))
        self.cli("predict", "--by", "Ann")
        with open(self.path(iv.DRAFT), "a", encoding="utf-8") as fh:
            fh.write("- **Other**: something else.\n    concern: x.\n    raises: reliability 1\n    addresses: none\n")
        self.cli("record", "--by", "Ann", "--answers", "Q1=Other", "--asked", ASKED)
        self.assertIn("Shown predictions: 0 of 1", self.cli("hits", "--by", "Ann").stdout)

    def test_multi_select_hits_only_on_an_exact_match(self):
        three = (CHEAP, STURDY, PRIVATE)
        self.round(question(1, choices=three, select="multi"), answers="Q1=2+3")
        self.round(question(1, choices=three, select="multi"), answers="Q1=2")
        self.assertIn("Shown predictions: 1 of 2", self.cli("hits", "--by", "Ann").stdout)

    def test_declined_questions_are_not_counted(self):
        self.round(question(1), answers="Q1=none")
        self.assertIn("Shown predictions: 0 of 0", self.cli("hits", "--by", "Ann").stdout)

    def test_hits_json_has_rounds(self):
        self.round(question(1), answers="Q1=2")
        self.round(question(1), question(2), answers="Q1=1, Q2=2")
        data = json.loads(self.cli("hits", "--by", "Ann", "--json").stdout)
        self.assertEqual(data["shown"], {"hits": 2, "total": 3})
        self.assertEqual([r["round"] for r in data["rounds"]], [1, 2])
        self.assertEqual(data["rounds"][1], {"round": 2, "shown": 1, "stated": 1, "total": 2})


class Domains(Case):
    def test_the_catalog_has_30_concerns_in_the_seven_domains(self):
        entries = iv.catalog()
        self.assertEqual(len(entries), 30)
        self.assertEqual(len({e.name for e in entries}), 30)
        tags = [t for e in entries for t in e.tags]
        self.assertEqual(len(tags), len(set(tags)))
        for e in entries:
            self.assertTrue(e.meaning and e.tags and e.domains, e.name)
            self.assertLessEqual(set(e.domains), set(iv.DOMAINS), e.name)
        self.assertEqual({d for e in entries for d in e.domains}, set(iv.DOMAINS))

    def test_the_first_16_are_the_3_1_0_seed(self):
        self.assertEqual([e.name for e in iv.catalog()[:16]], [
            "security", "open source", "owner control", "privacy", "user friction", "platform reach",
            "maintenance and operations", "effort", "performance", "reliability", "scalability",
            "interoperability", "flexibility", "cost", "third-party dependency", "testability"])

    def test_software_numbers_as_3_1_0_then_accessibility(self):
        os.remove(self.path(iv.WEIGHTS))
        self.cli("domains", "add", "software")
        self.assertTrue(self.read(iv.WEIGHTS).startswith(iv.WEIGHTS_TITLE + "\n\ndomains: software\n\n## C1 security\n"))
        titles = [c.title for c in self.state().concerns]
        self.assertEqual(len(titles), 17)
        self.assertEqual((titles[7], titles[9], titles[16]), ("C8 effort", "C10 reliability", "C17 accessibility"))

    def test_two_domains_give_each_concern_once(self):
        os.remove(self.path(iv.WEIGHTS))
        self.cli("domains", "add", "software", "fiction")
        want = [e.name for e in iv.catalog() if {"software", "fiction"} & set(e.domains)]
        self.assertEqual([c.name for c in self.state().concerns], want)

    def test_a_later_domain_appends_and_keeps_numbers(self):
        os.remove(self.path(iv.WEIGHTS))
        self.cli("domains", "add", "software")
        before = [c.title for c in self.state().concerns]
        self.cli("domains", "add", "fiction")
        after = [c.title for c in self.state().concerns]
        self.assertEqual(after[:17], before)
        self.assertEqual(after[17], "C18 clarity")
        self.assertIn("domains: software, fiction\n", self.read(iv.WEIGHTS))

    def test_a_weights_file_without_a_domains_line_gets_one(self):
        self.cli("domains", "add", "research")
        self.assertTrue(self.read(iv.WEIGHTS).startswith(
            iv.WEIGHTS_TITLE + "\n\ndomains: research\n\n## C1 reliability\n"))

    def test_an_unknown_domain_is_refused(self):
        before = self.read(iv.WEIGHTS)
        self.assertIn("software", self.cli("domains", "add", "poetry", ok=False).stderr)
        self.assertEqual(self.read(iv.WEIGHTS), before)

    def test_domains_lists_the_catalog(self):
        out = self.cli("domains").stdout
        self.assertIn("Domains in use: none", out)
        self.assertIn("software: 17 concerns", out)

    def test_a_bad_domain_line_fails_parse(self):
        self.write(iv.WEIGHTS, WEIGHTS.replace("\n\n## C1", "\n\ndomains: poetry\n\n## C1", 1))
        self.assertIn("not a domain", self.cli("parse", ok=False).stdout)

    def test_commands_without_weights_say_to_choose_domains(self):
        os.remove(self.path(iv.WEIGHTS))
        for command in ("concerns", "predict", "fit", "hits"):
            self.assertIn("domains add", self.cli(command, "--by", "Ann", ok=False).stderr)

    def test_tag_catalog_pulls_in_the_concern(self):
        self.cli("tag", "NEW:clarity", "--catalog")
        self.assertIn("## C4 clarity\nmeaning: the reader understands it the first time.\n"
                      "tags: clarity, NEW:clarity\n", self.read(iv.WEIGHTS))

    def test_tag_catalog_refuses_a_concern_already_there(self):
        self.assertIn("C1", self.cli("tag", "NEW:reliability", "--catalog", ok=False).stderr)

    def test_concerns_points_a_new_tag_to_the_catalog(self):
        self.write(iv.DRAFT, draft(question(1, choices=(("Fast (Recommended)", "NEW:pacing 2", "impl-effort 1"),
                                                        STURDY))))
        out = self.cli("concerns", "--by", "Ann").stdout
        self.assertIn("NEW:pacing", out)
        self.assertIn("refiner.py tag NEW:pacing --catalog", out)


class Exempting(Case):
    def test_exempt_appends_a_line(self):
        self.cli("exempt", "--question", "Merge or open a PR?", "--reason", "a menu, no trade-off", "--by", "Ann",
                 "--asked", ASKED)
        self.assertEqual(self.read(iv.EXEMPT), iv.EXEMPT_TITLE + "\n\n- 2026-10-02 10:00:00 +0000 · by: Ann · "
                                                                 "question: Merge or open a PR? · reason: a menu, no trade-off\n")
        self.cli("parse")

    def test_a_question_in_the_round_cannot_be_exempted(self):
        self.write(iv.DRAFT, draft(question(1)))
        result = self.cli("exempt", "--question", "Which way?", "--reason", "x", "--by", "Ann", ok=False)
        self.assertIn(iv.DRAFT, result.stderr)
        self.assertFalse(os.path.exists(self.path(iv.EXEMPT)))

    def test_the_separator_is_refused(self):
        result = self.cli("exempt", "--question", "A · B?", "--reason", "x", "--by", "Ann", ok=False)
        self.assertIn("--question must be one line", result.stderr)
        self.assertFalse(os.path.exists(self.path(iv.EXEMPT)))

    def test_a_bad_exempt_line_fails_parse(self):
        self.write(iv.EXEMPT, iv.EXEMPT_TITLE + "\n\n- yesterday · question: x\n")
        self.assertIn("an exempt line is", self.cli("parse", ok=False).stdout)

    def test_hits_ignore_exempt_questions(self):
        self.round(question(1), answers="Q1=1")
        before = self.cli("hits", "--by", "Ann", "--json").stdout
        self.cli("exempt", "--question", "Merge?", "--reason", "a menu", "--by", "Ann")
        self.assertEqual(self.cli("hits", "--by", "Ann", "--json").stdout, before)

    def test_passable_is_predicted_and_recent_exempt(self):
        self.write(iv.DRAFT, draft(question(1)))
        self.cli("predict", "--by", "Ann")
        self.write(iv.DRAFT, self.read(iv.DRAFT) + "\n" + question(2, text="Not predicted?"))
        for text, at in (("Recent?", "2026-10-02 10:25:00 +0000"), ("Old?", "2026-10-02 10:10:00 +0000")):
            self.cli("exempt", "--question", text, "--reason", "a menu", "--by", "Ann", "--asked", at)
        now = datetime.datetime(2026, 10, 2, 10, 30, tzinfo=datetime.timezone.utc)
        self.assertEqual(iv.passable(self.state(), now), {"Which way?", "Recent?"})


class Migration(Case):
    def legacy(self, folder="skel", log=LEGACY_LOG, weights=LEGACY_WEIGHTS):
        d = os.path.join(self.dir, folder)
        os.makedirs(d, exist_ok=True)
        for name, text in ((iv.LEGACY_LOG, log), (iv.LEGACY_WEIGHTS, weights)):
            with open(os.path.join(d, name), "w", encoding="utf-8", newline="") as fh:
                fh.write(text)
        return d

    def empty_store(self):
        os.remove(self.path(iv.WEIGHTS))

    def test_import_copies_the_files_and_keeps_the_originals(self):
        self.empty_store()
        d = self.legacy()
        self.cli("import", d)
        self.assertEqual(self.read(iv.LOG), LOG_RECORD)
        self.assertEqual(self.read(iv.WEIGHTS),
                         WEIGHTS.replace(iv.WEIGHTS_TITLE + "\n", iv.WEIGHTS_TITLE + "\n\ndomains: software\n", 1))
        with open(os.path.join(d, iv.LEGACY_LOG), encoding="utf-8", newline="") as fh:
            self.assertEqual(fh.read(), LEGACY_LOG)
        with open(os.path.join(d, iv.MOVED), encoding="utf-8") as fh:
            self.assertIn("They are no longer updated.", fh.read())
        self.cli("parse")

    def test_import_keeps_crlf(self):
        self.empty_store()
        d = self.legacy(log=LEGACY_LOG.replace("\n", "\r\n"), weights=LEGACY_WEIGHTS.replace("\n", "\r\n"))
        self.cli("import", d)
        self.assertEqual(self.read(iv.LOG), LOG_RECORD.replace("\n", "\r\n"))
        self.assertIn("\r\ndomains: software\r\n", self.read(iv.WEIGHTS))

    def test_import_refuses_a_store_with_history(self):
        d = self.legacy()
        before = self.read(iv.WEIGHTS)
        self.assertIn("already has", self.cli("import", d, ok=False).stderr)
        self.assertEqual(self.read(iv.WEIGHTS), before)
        self.assertFalse(os.path.exists(os.path.join(d, iv.MOVED)))

    def test_import_needs_legacy_files(self):
        self.empty_store()
        d = os.path.join(self.dir, "skel")
        os.mkdir(d)
        self.assertIn("no skel 3.1.0", self.cli("import", d, ok=False).stderr)

    def test_import_writes_nothing_when_a_file_would_not_parse(self):
        self.empty_store()
        d = self.legacy(log=LEGACY_LOG.replace("- <sel> **Cheap", "- **Cheap"))
        self.assertIn("nothing written", self.cli("import", d, ok=False).stderr)
        for name in (iv.LOG, iv.WEIGHTS):
            self.assertFalse(os.path.exists(self.path(name)))
        self.assertFalse(os.path.exists(os.path.join(d, iv.MOVED)))

    def test_import_moves_a_left_over_round(self):
        self.empty_store()
        d = self.legacy()
        with open(os.path.join(d, iv.LEGACY_DRAFT), "w", encoding="utf-8") as fh:
            fh.write(draft(question(1)).replace(iv.DRAFT_TITLE, "# skel interview round"))
        self.cli("import", d)
        self.assertEqual(self.read(iv.DRAFT), draft(question(1)))

    def test_outside_git_only_the_root_and_skel_are_searched(self):
        self.legacy("skel")
        self.legacy(os.path.join("docs", "design"))
        self.assertEqual(iv.legacy_folders(self.dir), ["skel"])

    def test_outside_git_another_repository_is_not_searched(self):
        nested = os.path.join(self.dir, "projects", "foo")
        os.makedirs(nested)
        subprocess.run(["git", "init", "-q", nested], check=True)
        self.legacy(os.path.join("projects", "foo", "skel"))
        self.assertEqual(iv.legacy_folders(self.dir), [])

    def test_legacy_folders_in_git_see_uncommitted_files(self):
        subprocess.run(["git", "init", "-q", self.dir], check=True)
        self.legacy()
        self.assertEqual(iv.legacy_folders(self.dir), ["skel"])

    def test_an_imported_folder_is_not_legacy(self):
        self.empty_store()
        self.cli("import", self.legacy())
        self.assertEqual(iv.legacy_folders(self.dir), [])

    def test_the_store_is_at_the_git_root(self):
        subprocess.run(["git", "init", "-q", self.dir], check=True)
        sub = os.path.join(self.dir, "a", "b")
        os.makedirs(sub)
        self.assertEqual(os.path.realpath(iv.store_for(sub)), os.path.realpath(os.path.join(self.dir, iv.STORE)))

    def test_domains_add_refuses_while_data_is_unmigrated(self):
        self.empty_store()
        self.legacy()
        self.assertIn("refiner.py import", self.cli("domains", "add", "software", ok=False).stderr)
        self.assertFalse(os.path.exists(self.path(iv.WEIGHTS)))

    def test_domains_add_fresh_sets_the_old_data_aside(self):
        self.empty_store()
        d = self.legacy()
        self.cli("domains", "add", "software", "--fresh")
        with open(os.path.join(d, iv.MOVED), encoding="utf-8") as fh:
            self.assertIn("a fresh start was chosen", fh.read())
        self.assertEqual(iv.legacy_folders(self.dir), [])


class Docs(unittest.TestCase):
    def read(self):
        with open(os.path.join(SKILL, "SKILL.md"), encoding="utf-8") as fh:
            return fh.read()

    def test_the_skill_has_front_matter(self):
        self.assertTrue(self.read().startswith("---\nname: question-refiner\ndescription: "))

    def test_the_skill_names_every_command(self):
        text = self.read()
        for command in ("parse", "domains", "concerns", "tag", "rate", "predict", "record", "fit", "hits", "exempt",
                        "import"):
            self.assertIn(f"refiner.py\" {command}", text)

    def test_the_skill_confirms_inferred_domains(self):
        text = self.read()
        for words in ("Use these (Recommended)", "Change them", "(inferred)", "[x]", "choosing domains"):
            self.assertIn(words, text)

    def test_the_skill_says_a_fresh_start_is_the_users_choice(self):
        text = self.read()
        self.assertIn("only when the user chooses a fresh start", text)
        self.assertIn("migrating data deferred", text)

    def test_the_skill_says_to_ask_without_marks(self):
        self.assertIn("without its `<probe>` mark", self.read())

    def test_the_skill_keeps_the_round_out_of_git(self):
        self.assertIn("add `.question-refiner/round.md` to `.gitignore`", self.read())

    def test_the_readme_describes_the_plugin(self):
        root = os.path.join(SKILL, "..", "..", "..", "..")
        with open(os.path.join(root, "README.md"), encoding="utf-8") as fh:
            readme = fh.read()
        with open(os.path.join(SKILL, "..", "..", "hooks", "rule.txt"), encoding="utf-8") as fh:
            words = len(fh.read().split())
        self.assertIn("\n## question-refiner\n", readme)
        self.assertIn("/plugin install question-refiner@hanoixan-claude-plugins", readme)
        self.assertIn(f"| yes | {words} words |", readme.split("[question-refiner](#question-refiner) |", 1)[1]
                      .split("\n", 1)[0])
        self.assertNotIn("interview.py", readme)


class ReviewFixes(Case):
    def test_a_draft_with_log_only_lines_is_refused(self):
        text = draft(question(1)).replace("Which way?", "<tracer> Which way?") + "axis: C2 effort vs C1 reliability\n"
        self.write(iv.DRAFT, text)
        result = self.cli("predict", "--by", "Ann", ok=False)
        self.assertIn("only `record` writes", result.stderr)
        self.assertEqual(self.read(iv.DRAFT), text)

    def test_a_name_with_the_separator_is_refused(self):
        before = self.read(iv.WEIGHTS)
        result = self.cli("rate", "C2=4", "--by", "A · B", ok=False)
        self.assertIn("--by", result.stderr)
        self.assertEqual(self.read(iv.WEIGHTS), before)

    def test_a_bad_new_concern_name_is_refused(self):
        before = self.read(iv.WEIGHTS)
        for name in ("", "a\nb"):
            self.cli("tag", "offline", "--new", name, "works offline.", ok=False)
        self.cli("tag", "offline", "--new", "offline", "a\nb", ok=False)
        self.assertEqual(self.read(iv.WEIGHTS), before)

    def test_record_refuses_a_person_other_than_the_predicted_one(self):
        text = WEIGHTS
        for ann in ("rating: 10 · by: Ann · 2026-10-01\n", "rating: 1 · by: Ann · 2026-10-01\n"):
            text = text.replace(ann, ann + "rating: 5 · by: Bob · 2026-10-01\n")
        self.write(iv.WEIGHTS, text)
        self.write(iv.DRAFT, draft(question(1)))
        self.cli("predict", "--by", "Ann")
        result = self.cli("record", "--by", "Bob", "--answers", "Q1=1", "--asked", ASKED, ok=False)
        self.assertIn("predicted for Ann", result.stderr)
        self.assertFalse(os.path.exists(self.path(iv.LOG)))

    def test_record_refuses_a_prediction_that_names_no_choice(self):
        self.write(iv.DRAFT, draft(question(1)))
        self.cli("predict", "--by", "Ann")
        self.write(iv.DRAFT, self.read(iv.DRAFT).replace("**Sturdy**", "**Strong**"))
        result = self.cli("record", "--by", "Ann", "--answers", "Q1=1", "--asked", ASKED, ok=False)
        self.assertIn("run `refiner.py predict` again", result.stderr)

    def test_record_refuses_a_prediction_without_concern_only(self):
        self.write(iv.DRAFT, draft(question(1)))
        self.cli("predict", "--by", "Ann")
        self.write(iv.DRAFT, "".join(l for l in self.read(iv.DRAFT).splitlines(keepends=True)
                                     if not l.startswith("concern-only:")))
        result = self.cli("record", "--by", "Ann", "--answers", "Q1=1", "--asked", ASKED, ok=False)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn("run `refiner.py predict` again", result.stderr)

    def test_the_reference_says_a_renamed_user_is_a_new_person(self):
        with open(os.path.join(SKILL, "SKILL.md"), encoding="utf-8") as fh:
            self.assertIn("starts a new history", fh.read())


class DeferredMinors(Case):
    def test_a_round_number_in_other_digits_is_refused(self):
        self.write(iv.LOG, LOG_RECORD.replace("round: 1", "round: \u00b2"))
        self.assertIn("`round:` is a number", self.cli("parse", ok=False).stdout)
        self.assertNotIn("Traceback", self.cli("hits", "--by", "Ann", ok=False).stderr)

    def test_an_answer_in_other_digits_is_refused(self):
        self.write(iv.DRAFT, draft(question(1)))
        self.cli("predict", "--by", "Ann")
        result = self.cli("record", "--by", "Ann", "--answers", "Q1=\u00b2", "--asked", ASKED, ok=False)
        self.assertNotIn("Traceback", result.stderr)
        self.assertFalse(os.path.exists(self.path(iv.LOG)))

    def test_a_label_with_the_choice_separator_is_refused(self):
        self.write(iv.DRAFT, draft(question(1, choices=(("Cheap | quick", *CHEAP[1:]), STURDY))))
        result = self.cli("predict", "--by", "Ann", ok=False)
        self.assertIn("` | `", result.stderr)

    def test_a_concern_rated_twice_in_one_call_is_refused(self):
        before = self.read(iv.WEIGHTS)
        result = self.cli("rate", "C2=3", "C2=7", "--by", "Ann", ok=False)
        self.assertIn("C2 is rated twice", result.stderr)
        self.assertEqual(self.read(iv.WEIGHTS), before)

    def test_a_rewritten_file_keeps_its_mode(self):
        os.chmod(self.path(iv.WEIGHTS), 0o644)
        self.cli("rate", "C2=4", "--by", "Ann")
        self.assertEqual(os.stat(self.path(iv.WEIGHTS)).st_mode & 0o777, 0o644)

    def test_a_new_file_gets_the_usual_mode(self):
        umask = os.umask(0)
        os.umask(umask)
        self.round(question(1), answers="Q1=1")
        self.assertEqual(os.stat(self.path(iv.LOG)).st_mode & 0o777, 0o666 & ~umask)

    def test_a_round_recorded_twice_is_refused(self):
        self.write(iv.DRAFT, draft(question(1)))
        self.cli("predict", "--by", "Ann")
        predicted = self.read(iv.DRAFT)
        self.cli("record", "--by", "Ann", "--answers", "Q1=1", "--asked", ASKED)
        log = self.read(iv.LOG)
        self.write(iv.DRAFT, predicted)
        result = self.cli("record", "--by", "Ann", "--answers", "Q1=1", "--asked", ASKED, ok=False)
        self.assertIn("already in", result.stderr)
        self.assertEqual(self.read(iv.LOG), log)
        self.cli("predict", "--by", "Ann")
        self.cli("record", "--by", "Ann", "--answers", "Q1=1", "--asked", ASKED, ok=False)
        self.assertEqual(self.read(iv.LOG), log)

    def test_the_same_round_predicted_again_is_recorded(self):
        for _ in range(2):
            self.round(question(1), answers="Q1=1")
        self.assertEqual(len(self.state().log), 2)

    def test_parse_and_tag_take_by(self):
        self.cli("parse", "--by", "Ann")
        self.cli("tag", "offline", "C3", "--by", "Ann")

    def test_the_reference_example_axis_is_what_record_writes(self):
        with open(os.path.join(SKILL, "SKILL.md"), encoding="utf-8") as fh:
            doc = fh.read()
        block = doc.split("```text\n## Q14\n", 1)[1].split("```", 1)[0]
        recs, problems = records(iv.LOG_TITLE + "\n\n## Q1\n" + block, iv.LOG_TITLE)
        self.assertEqual(problems.errors, [])
        rec = recs[0]
        os.remove(self.path(iv.WEIGHTS))
        self.cli("domains", "add", "software")
        concerns = self.state().concerns
        tags, by_id = iv.tag_map(concerns), {c.cid: c for c in concerns}
        a = iv.axis(iv.vector(rec.selected()[0], tags), iv.vector(rec.choice(rec.fields["concern-only"]), tags))
        self.assertEqual(rec.fields["axis"], iv.axis_text(a, by_id))


class BranchMinors(Case):
    def legacy(self, folder="skel", log=LEGACY_LOG):
        return Migration.legacy(self, folder, log=log)

    def test_a_dot_inside_a_name_or_question_is_accepted(self):
        self.cli("rate", "C2=4", "--by", "A·B")
        self.cli("exempt", "--question", "Pick A·B?", "--reason", "a menu", "--by", "A·B")
        self.cli("parse")
        self.assertIn("Pick A·B?", iv.passable(self.state(), datetime.datetime.now().astimezone()))

    def test_a_dot_at_either_end_of_a_name_is_refused(self):
        before = self.read(iv.WEIGHTS)
        for name in ("A ·", "· A", "A · B"):
            self.assertIn("--by", self.cli("rate", "C2=4", "--by", name, ok=False).stderr)
        self.assertEqual(self.read(iv.WEIGHTS), before)

    def test_domains_add_with_dir_searches_the_stores_repository(self):
        subprocess.run(["git", "init", "-q", self.dir], check=True)
        self.legacy()
        store = os.path.join(self.dir, "sub", iv.STORE)
        result = subprocess.run([sys.executable, SCRIPT, "domains", "add", "software", "--dir", store],
                                capture_output=True, text=True, cwd=self.dir)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(f'import "{os.path.join(os.path.realpath(self.dir), "skel")}"',
                      result.stderr.replace(self.dir, os.path.realpath(self.dir)))
        self.assertFalse(os.path.exists(os.path.join(store, iv.WEIGHTS)))

    def test_the_legacy_search_asks_git_for_the_two_names_only(self):
        calls = []
        real = iv.subprocess.run

        def run(argv, **kw):
            calls.append(argv)
            return real(argv, **kw)
        iv.subprocess.run = run
        self.addCleanup(setattr, iv.subprocess, "run", real)
        iv.legacy_folders(self.dir)
        self.assertEqual(calls[0][-3:], ["--", f":(glob)**/{iv.LEGACY_LOG}", f":(glob)**/{iv.LEGACY_WEIGHTS}"])

    def test_legacy_data_at_the_root_and_in_skel_is_found_in_git(self):
        subprocess.run(["git", "init", "-q", self.dir], check=True)
        self.legacy(".")
        self.legacy("skel")
        self.assertEqual(iv.legacy_folders(self.dir), [".", "skel"])

    def test_import_refuses_a_store_with_a_round(self):
        os.remove(self.path(iv.WEIGHTS))
        self.write(iv.DRAFT, draft(question(1)))
        result = self.cli("import", self.legacy(), ok=False)
        self.assertIn(iv.DRAFT, result.stderr)
        self.assertEqual(self.read(iv.DRAFT), draft(question(1)))
        self.assertFalse(os.path.exists(self.path(iv.LOG)))

    def test_import_leaves_out_a_round_already_logged(self):
        self.write(iv.DRAFT, draft(question(1)))
        self.cli("predict", "--by", "Ann")
        predicted = self.read(iv.DRAFT)
        round_id = next(l for l in predicted.splitlines() if l.startswith("round-id: "))
        os.remove(self.path(iv.WEIGHTS))
        os.remove(self.path(iv.DRAFT))
        d = self.legacy(log=LEGACY_LOG + round_id + "\n")
        with open(os.path.join(d, iv.LEGACY_DRAFT), "w", encoding="utf-8") as fh:
            fh.write(predicted.replace(iv.DRAFT_TITLE, "# skel interview round"))
        result = self.cli("import", d)
        self.assertFalse(os.path.exists(self.path(iv.DRAFT)))
        self.assertIn("already recorded", result.stdout)
        self.assertTrue(os.path.exists(self.path(iv.LOG)))

    def test_no_line_is_wider_than_120_columns(self):
        hooks = os.path.join(SKILL, "..", "..", "hooks")
        for path in (SCRIPT, os.path.join(hooks, "gate.py"), os.path.join(hooks, "detect.py")):
            with open(path, encoding="utf-8") as fh:
                for k, line in enumerate(fh, 1):
                    self.assertLessEqual(len(line.rstrip("\n")), 120, f"{path}:{k}")

    def test_the_readme_names_every_command(self):
        with open(os.path.join(SKILL, "..", "..", "..", "..", "README.md"), encoding="utf-8") as fh:
            section = fh.read().split("\n## question-refiner\n", 1)[1].split("\n## ", 1)[0]
        for command in ("parse", "domains add", "concerns", "tag", "rate", "predict", "record", "exempt", "fit",
                        "hits", "import"):
            self.assertIn(f"\nrefiner.py {command} ", section)
        self.assertRegex(section, r"\nrefiner\.py domains {2,}\S")

    def test_the_skill_says_what_to_do_without_python3(self):
        with open(os.path.join(SKILL, "SKILL.md"), encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("If `refiner.py` cannot run", text)
        self.assertIn("ask directly", text)


class Probability(Case):
    def predicted(self, *questions):
        self.write(iv.DRAFT, draft(*questions))
        out = self.cli("predict", "--by", "Ann").stdout
        return out, {r.number: r for r in self.state().draft}

    def test_two_choices_log_the_softmax_probability(self):
        out, recs = self.predicted(question(1))
        self.assertIn("· gap 36 · p 97% · model: stated", recs[1].fields["prediction"])
        self.assertIn("Q1: Sturdy (lead 36, p 97%)", out)
        self.assertEqual(iv.logged_p(recs[1]), 97)

    def test_three_choices_share_the_probability(self):
        _, recs = self.predicted(question(1, choices=(CHEAP, STURDY, PRIVATE)))
        self.assertEqual(iv.logged_p(recs[1]), 61)

    def test_multi_select_has_no_probability(self):
        _, recs = self.predicted(question(1, choices=(CHEAP, STURDY, PRIVATE), select="multi"))
        self.assertNotIn(" p ", recs[1].fields["prediction"])
        self.assertIsNone(iv.logged_p(recs[1]))

    def test_probability_includes_the_recommended_bonus(self):
        self.assertAlmostEqual(iv.probability([18.0, -18.0], 0), 1 / (1 + math.exp(-3.6)))

    def test_a_logged_prediction_without_p_still_parses(self):
        self.write(iv.LOG, LOG_RECORD)
        self.cli("parse")
        self.assertIsNone(iv.logged_p(self.state().log[0]))


class Threshold(Case):
    def test_the_default_is_off(self):
        self.assertEqual(iv.threshold_of(self.state().weights_lines, "Ann"), 100)
        self.assertIn("threshold for Ann: off", self.cli("auto", "--by", "Ann").stdout)

    def test_setting_writes_a_line_and_the_latest_counts(self):
        self.cli("auto", "80", "--by", "Ann")
        self.cli("auto", "70", "--by", "Ann")
        self.assertIn("threshold: 70 · by: Ann · ", self.read(iv.WEIGHTS))
        self.assertEqual(iv.threshold_of(self.state().weights_lines, "Ann"), 70)
        self.cli("parse")
        self.assertIn("threshold for Ann: 70", self.cli("auto", "--by", "Ann").stdout)

    def test_another_persons_threshold_does_not_apply(self):
        self.cli("auto", "0", "--by", "Bob")
        self.assertEqual(iv.threshold_of(self.state().weights_lines, "Ann"), 100)

    def test_the_threshold_is_0_to_100(self):
        before = self.read(iv.WEIGHTS)
        for bad in ("101", "-1", "8.5", "x"):
            self.assertIn("0 to 100", self.cli("auto", bad, "--by", "Ann", ok=False).stderr)
        self.assertEqual(self.read(iv.WEIGHTS), before)
        self.cli("auto", "0", "--by", "Ann")
        self.cli("auto", "100", "--by", "Ann")

    def test_a_bad_threshold_line_does_not_parse(self):
        self.write(iv.WEIGHTS, WEIGHTS.replace("\n\n## C1", "\nthreshold: 120 · by: Ann · 2026-10-20\n\n## C1", 1))
        self.assertIn("`threshold:` is", self.cli("parse", ok=False).stdout)

    def test_the_line_goes_after_domains(self):
        os.remove(self.path(iv.WEIGHTS))
        self.cli("domains", "add", "software")
        self.cli("auto", "80", "--by", "Ann")
        text = self.read(iv.WEIGHTS)
        self.assertIn("domains: software\nthreshold: 80 · by: Ann · ", text)
        self.cli("parse")


def logged(results, by="Ann"):
    """A log with one Cheap/Sturdy record per (hit, p) pair; Sturdy is predicted, p None leaves it off."""
    out = [iv.LOG_TITLE, ""]
    for n, (hit, p) in enumerate(results, 1):
        shown_p = f" · p {p}%" if p is not None else ""
        out += [f"## Q{n}", "Which way?",
                f"header: H · round: {n} · select: single · asked: {ASKED} · by: {by}",
                f"- {'' if hit else '<sel> '}**Cheap (Recommended)**: about cheap.",
                "    concern: a worry about cheap.", "    raises: reliability 2", "    addresses: impl-effort 2",
                f"- {'<sel> ' if hit else ''}* **Sturdy**: about sturdy.",
                "    concern: a worry about sturdy.", "    raises: impl-effort 2", "    addresses: reliability 2",
                f"prediction: Sturdy · score 18 · gap 36{shown_p} · model: stated", "concern-only: Sturdy", ""]
    return "\n".join(out)


class Tally(Case):
    def tally(self):
        return self.cli("tally", "--by", "Ann").stdout.strip()

    def test_before_8_answers_it_counts_down(self):
        self.write(iv.LOG, logged([(True, 97)] * 5))
        self.assertEqual(self.tally(), "Predictions: 5 answered, 3 more before the tally and auto-answering start")

    def test_the_line_counts_recent_and_all(self):
        self.write(iv.LOG, logged([(False, 61)] * 10 + [(True, 97)] * 50))
        self.assertEqual(self.tally(), "Predictions: 50 of 50 recent (100%), 50 of 60 all (83%) · threshold off")

    def test_misses_give_the_mean_spread_and_suggestion(self):
        self.write(iv.LOG, logged([(True, 97)] * 8 + [(False, 61), (False, 61)]))
        self.assertEqual(self.tally(), "Predictions: 8 of 10 recent (80%), 8 of 10 all (80%) · misses at p 61% ± 0 (2) "
                                       "· threshold off (suggested: 61)")

    def test_one_miss_has_no_spread_or_suggestion(self):
        self.write(iv.LOG, logged([(True, 97)] * 8 + [(False, 87)]))
        self.assertIn("· misses at p 87% (1) · threshold off", self.tally())
        self.assertNotIn("suggested", self.tally())

    def test_the_suggestion_is_capped_at_99(self):
        self.write(iv.LOG, logged([(True, 97)] * 8 + [(False, 97), (False, 87)]))
        self.assertIn("misses at p 92% ± 7 (2) · threshold off (suggested: 99)", self.tally())

    def test_misses_without_p_count_as_misses_only(self):
        self.write(iv.LOG, logged([(True, 97)] * 8 + [(False, None)]))
        self.assertEqual(self.tally(), "Predictions: 8 of 9 recent (89%), 8 of 9 all (89%) · threshold off")

    def test_the_threshold_shows(self):
        self.write(iv.LOG, logged([(True, 97)] * 8))
        self.cli("auto", "80", "--by", "Ann")
        self.assertTrue(self.tally().endswith("· threshold 80"))
        self.assertIn("Predictions: 8 of 8 recent", self.cli("auto", "--by", "Ann").stdout)

    def test_json(self):
        self.write(iv.LOG, logged([(True, 97)] * 8 + [(False, 61), (False, 61)]))
        data = json.loads(self.cli("tally", "--by", "Ann", "--json").stdout)
        self.assertEqual(data["recent"], {"hits": 8, "total": 10})
        self.assertEqual(data["misses"]["count"], 2)
        self.assertEqual(data["suggested"], 61)

    def test_record_prints_the_tally_last(self):
        out = self.round(question(1), answers="Q1=2").stdout.strip().splitlines()
        self.assertEqual(out[-1], "Predictions: 1 answered, 7 more before the tally and auto-answering start")


if __name__ == "__main__":
    unittest.main()
