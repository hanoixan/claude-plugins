import os
import re
import shutil
import subprocess
import unittest
import zipfile

from support import S_ACT1, S_ACT2, S_ACT3, S_PREMISE, SKILL, ScriptCase

import wrist_profile as wp


class ScreenplayProfile(unittest.TestCase):
    def setUp(self):
        self.p = wp.load_profile("screenplay")
        self.p.set_premise({"acts": "3", "act_headings": "no"})

    def test_file_shape(self):
        self.assertEqual([path for path, _ in self.p.expected_files("the-third-bell")],
                         ["synopsis.md", "outline.md", "character.md", "misc.md",
                          "work/act-1.md", "work/act-2.md", "work/act-3.md"])

    def test_premise_keys(self):
        self.assertEqual(self.p.premise_keys["acts"], {"type": "int", "min": 1, "max": 7, "required": True})
        self.assertEqual(self.p.premise_keys["act_headings"]["type"], "bool")

    def test_a_screenplay_has_a_title_page_fountain_lint_and_its_own_style(self):
        self.assertIs(self.p.title_page, True)
        self.assertEqual(self.p.lint_format, "fountain")
        self.assertEqual(self.p.publish_style, "screenplay")

    def test_acts_are_a_sequence_with_established_and_no_printed_heading(self):
        spec = self.p.functions["act"]
        self.assertTrue(spec["sequence"])
        self.assertTrue(spec["prose"])
        self.assertEqual(spec["required_when_realized"], ["Established"])
        self.assertIsNone(spec["heading_field"])
        self.assertEqual(spec["fields"], ["Pages"])
        self.assertEqual(spec["children"]["scene"], ["Purpose", "Location", "Pages", "Must include", "Must avoid"])

    def test_the_registries(self):
        self.assertEqual(self.p.functions["outline"]["children"]["beat"], ["Purpose", "Change", "Pages"])
        self.assertEqual(self.p.functions["misc"]["children"]["location"], ["Slug", "Facts"])
        for kind in ("prop", "concept", "timeline"):
            self.assertEqual(self.p.functions["misc"]["children"][kind], ["Facts"])

    def test_only_the_acts_are_prose(self):
        self.assertEqual([n for n, s in self.p.functions.items() if s["prose"]], ["act"])

    def test_questions(self):
        required = {q.id for q in self.p.questions if q.required}
        self.assertEqual(required, {"genre", "premise", "ending", "tone", "audience", "format", "runtime", "acts",
                                    "story"})
        deferrable = {q.id for q in self.p.questions if not q.required}
        self.assertEqual(deferrable, {"setting", "locations", "themes", "comps", "characters", "events", "fixed",
                                      "structure", "avoid", "act-headings"})

    def test_every_premise_key_has_a_question(self):
        self.assertEqual({self.p.question_key(q.id) for q in self.p.questions} - {None}, set(self.p.premise_keys))


class ScreenplayContent(unittest.TestCase):
    def read(self, name):
        with open(os.path.join(SKILL, "profiles", "screenplay", name), encoding="utf-8") as fh:
            return fh.read()

    def test_structures(self):
        text = self.read("structures.md")
        for name in ("Aristotle", "Syd Field", "Hero's Journey", "Save the Cat!", "Sequence approach",
                     "Story Circle", "22 steps", "Kishōtenketsu"):
            self.assertIn(name, text)
        sections = text.split("\n## ")[1:]
        for section in sections:
            title = section.split("\n")[0]
            if title.startswith("Formats"):
                continue
            self.assertIn("**Best for:**", section, title)
            self.assertIn("**Pages in a 120-page feature:**", section, title)
            self.assertIn("**Pages in a 10-page short:**", section, title)

    def test_the_format_table(self):
        text = self.read("structures.md")
        for needle in ("feature", "short", "TV-style", "act_headings"):
            self.assertIn(needle, text)

    def test_quality_has_its_parts(self):
        text = self.read("quality.md")
        for heading in ("## Clichés and stock moves", "## Marks of low quality", "## Judgment checklist"):
            self.assertIn(heading, text)
        self.assertGreaterEqual(text.count("- [ ] "), 14)
        for phrase in ("runtime", "slug line", "Established", "subtext"):
            self.assertIn(phrase, text)

    def test_every_lint_pattern_matches_its_positive_and_not_its_negative(self):
        items = wp.load_profile("screenplay").lint_items()
        self.assertGreaterEqual(len(items), 16)
        ids = [i["id"] for i in items]
        self.assertEqual(len(ids), len(set(ids)))
        for item in items:
            with self.subTest(item["id"]):
                rx = re.compile(item["pattern"], re.IGNORECASE)
                self.assertTrue(rx.search(item["positive"]), "positive sample does not match")
                self.assertFalse(rx.search(item["negative"]), "negative sample matches")

    def test_lint_scopes_are_fountain_scopes(self):
        scopes = {i["scope"] for i in wp.load_profile("screenplay").lint_items()}
        self.assertEqual(scopes, {"action", "dialogue", "anywhere"})


HAVE_TOOLS = shutil.which("pandoc") and shutil.which("typst")


class ThirdBellChecks(ScriptCase):
    def test_the_example_checks_clean(self):
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("7 stand-ins", out)
        self.assertIn("0 errors, 0 warnings", out)

    def test_every_gate_is_open(self):
        for phase in ("generation", "realization", "publishing"):
            code, out = self.run_wrist("gate", "wrist", phase)
            self.assertEqual(code, 0, out)

    def test_every_file_is_realized_and_lint_is_clean(self):
        _, out = self.run_wrist("status", "wrist")
        self.assertIn("Realized (7):", out)
        _, out = self.run_wrist("lint", "wrist")
        self.assertIn("0 hits in 0 files", out)

    def test_order_follows_the_profile(self):
        _, out = self.run_wrist("order", "wrist")
        names = [l.split()[1] for l in out.splitlines() if l[:1].isdigit()]
        self.assertEqual(names, ["synopsis.md", "outline.md", "character.md", "misc.md",
                                 "work/act-1.md", "work/act-2.md", "work/act-3.md"])

    def test_the_acts_are_real_fountain(self):
        import wrist_lint
        for n in (1, 2, 3):
            kinds = set(wrist_lint.elements(self.read(f"work/act-{n}.md")))
            self.assertLessEqual({"scene-heading", "action"}, kinds, n)
            if n < 3:                                   # act 3 is silent: the passenger never speaks
                self.assertLessEqual({"character", "dialogue"}, kinds, n)


class ThirdBellFileSet(ScriptCase):
    def test_review_focus_a_fourth_act_needs_its_stand_in(self):
        self.replace(S_PREMISE, "acts: 3", "acts: 4")
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("required stand-in missing: wrist/work/act-4.md.wrist.md", out)

    def test_review_focus_fewer_acts_leave_a_stand_in_outside_the_shape(self):
        self.replace(S_PREMISE, "acts: 3", "acts: 2")
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("outside the screenplay shape", out)

    def test_acts_out_of_range_or_missing_are_clear_errors(self):
        for value in ("0", "8", "three"):
            with self.subTest(value=value):
                self.replace(S_PREMISE, "acts: 3", f"acts: {value}")
                code, out = self.check()
                self.assertEqual(code, 1, out)
                self.assertIn("`acts:` must be a whole number from 1 to 7", out)
                self.assertIn(f"(got '{value}')", out)
                self.replace(S_PREMISE, f"acts: {value}", "acts: 3")
        self.replace(S_PREMISE, "acts: 3\n", "")
        code, out = self.check()
        self.assertIn("`acts:` is required (a whole number from 1 to 7)", out)

    def test_the_acts_and_act_headings_questions_are_answered_by_the_front_matter(self):
        code, out = self.check()
        self.assertNotIn("question 'acts'", out)
        self.assertNotIn("question 'act-headings'", out)


class ThirdBellContinuity(ScriptCase):
    def test_stamp_refuses_an_act_with_no_established_text(self):
        self.replace(S_ACT2, "- **Established:**", "- **Notes:**")
        code, out = self.run_wrist("stamp", "wrist", "work/act-2.md")
        self.assertEqual(code, 1, out)
        self.assertIn("no `Established:` text", out)

    def test_an_act_must_continue_the_one_before(self):
        self.replace(S_ACT3, "(continues)", "(mentions)")
        code, out = self.check()
        self.assertIn("no `Depends on:` link to work/act-2.md's stand-in with the relation `continues`", out)

    def test_editing_an_act_after_stamping_blocks_publishing(self):
        self.write("work/act-1.md", self.read("work/act-1.md") + "\nA stray line.\n")
        code, out = self.run_wrist("gate", "wrist", "publishing")
        self.assertIn("work/act-1.md is edited", out)

    def test_review_focus_lint_flags_a_cliche_in_action_but_not_the_same_words_in_dialogue(self):
        text = self.read("work/act-1.md")
        self.write("work/act-1.md", text + "\nMARIT\nWe see the problem, as you know.\n\nWe see a door open.\n")
        code, out = self.run_wrist("lint", "wrist")
        self.assertIn("[as-you-know]", out)
        self.assertIn("[we-see]", out)
        self.assertEqual(out.count("[we-see]"), 1)


class ThirdBellPublish(ScriptCase):
    @unittest.skipUnless(HAVE_TOOLS, "pandoc and typst are not installed")
    def test_the_example_publishes_with_act_headings(self):
        code, out = self.run_wrist("publish", "wrist")
        self.assertEqual(code, 0, out)
        with open(self.path("output/the-third-bell.pdf"), "rb") as fh:
            self.assertEqual(fh.read(5), b"%PDF-")
        with zipfile.ZipFile(self.path("output/the-third-bell.epub")) as z:
            text = "\n".join(z.read(n).decode("utf-8") for n in z.namelist() if n.endswith(".xhtml"))
        for needle in ("ACT ONE", "ACT TWO", "ACT THREE", "class=\"scene-heading\"", "class=\"character\""):
            self.assertIn(needle, text, needle)
        self.assertIn("First draft", text)
        self.assertEqual(sorted(os.listdir(self.path("output"))), ["the-third-bell.epub", "the-third-bell.pdf"])

    @unittest.skipUnless(HAVE_TOOLS, "pandoc and typst are not installed")
    def test_without_act_headings_the_epub_has_no_act_labels(self):
        self.replace(S_PREMISE, "act_headings: yes", "act_headings: no")
        code, out = self.run_wrist("publish", "wrist")
        self.assertEqual(code, 0, out)
        with zipfile.ZipFile(self.path("output/the-third-bell.epub")) as z:
            text = "\n".join(z.read(n).decode("utf-8") for n in z.namelist() if n.endswith(".xhtml"))
        self.assertNotIn("ACT ONE", text)

    @unittest.skipUnless(HAVE_TOOLS, "pandoc and typst are not installed")
    def test_a_failed_build_removes_the_act_markers(self):
        self.write("work/act-2.md", "INT. A - DAY\n\n\x00\x00\n")
        self.run_wrist("stamp", "wrist", "work/act-2.md")
        self.run_wrist("publish", "wrist")
        self.assertFalse([n for n in os.listdir(self.path("output")) if n.startswith(".wrist-act")]
                         if os.path.isdir(self.path("output")) else [])


if __name__ == "__main__":
    unittest.main()
