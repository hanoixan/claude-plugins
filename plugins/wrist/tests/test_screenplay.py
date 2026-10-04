import os
import re
import unittest

from support import SKILL

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


if __name__ == "__main__":
    unittest.main()
