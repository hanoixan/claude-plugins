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
        self.assertIn("prediction: Sturdy · score 18 · gap 36 · model: stated\n", text)
        self.assertIn("concern-only: Sturdy\n", text)
        self.assertIn("model: stated", result.stdout)

    def test_predict_refuses_an_unannotated_choice(self):
        self.write(iv.DRAFT, draft(question(1, annotated=False)))
        result = self.cli("predict", "--by", "Ann", ok=False)
        self.assertIn("not annotated", result.stderr)

    def test_predict_refuses_an_unmapped_tag(self):
        self.write(iv.DRAFT, draft(question(1, choices=(CHEAP, ("Offline", "offline 1", "reliability 1")))))
        result = self.cli("predict", "--by", "Ann", ok=False)
        self.assertIn("interview.py tag", result.stderr)

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
        self.assertIn("run `interview.py predict` first", result.stderr)

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


class Docs(unittest.TestCase):
    def read(self, *parts):
        with open(os.path.join(SKILL, *parts), encoding="utf-8") as fh:
            return fh.read()

    def test_the_reference_names_every_command(self):
        text = self.read("references", "interviewing.md")
        for command in ("parse", "concerns", "tag", "rate", "fit", "predict", "record", "hits"):
            self.assertIn(f"interview.py\" {command}", text)

    def test_every_place_that_asks_points_to_the_reference(self):
        self.assertGreaterEqual(self.read("SKILL.md").count("interviewing.md"), 3)
        self.assertIn("interviewing.md", self.read("references", "implementing.md"))
        self.assertIn("interviewing.md", self.read("references", "abstract-systems.md"))

    def test_the_system_template_has_principles(self):
        self.assertIn("## Principles", self.read("assets", "templates", "SYSTEM.md"))


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
        self.assertIn("run `interview.py predict` again", result.stderr)

    def test_record_refuses_a_prediction_without_concern_only(self):
        self.write(iv.DRAFT, draft(question(1)))
        self.cli("predict", "--by", "Ann")
        self.write(iv.DRAFT, "".join(l for l in self.read(iv.DRAFT).splitlines(keepends=True)
                                     if not l.startswith("concern-only:")))
        result = self.cli("record", "--by", "Ann", "--answers", "Q1=1", "--asked", ASKED, ok=False)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn("run `interview.py predict` again", result.stderr)

    def test_the_reference_says_a_renamed_user_is_a_new_person(self):
        with open(os.path.join(SKILL, "references", "interviewing.md"), encoding="utf-8") as fh:
            self.assertIn("starts a new history", fh.read())


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
