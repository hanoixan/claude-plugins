import os
import re
import unittest

from support import SKILL

import wrist_profile as wp
import wrist_verse

PROFILE_DIR = os.path.join(SKILL, "profiles", "poem")


def fake(**extra):
    data = {"name": "t", "files": [{"path": "s.md", "function": "a", "order": 1},
                                   {"path": "work/{slug}.md", "function": "a", "order": 2}],
            "functions": {"a": {"heading": "a", "prose": True}}, "relations": [], "limits": {"max_prose_words": 5}}
    data.update(extra)
    return data


class FormSetting(unittest.TestCase):
    def test_a_form_names_two_listed_paths(self):
        p = wp.parse_profile(fake(form={"structure": "s.md", "poem": "work/{slug}.md"}))
        self.assertEqual(p.form, {"structure": "s.md", "poem": "work/{slug}.md"})
        self.assertEqual(p.form_paths("night"), ("s.md", "work/night.md"))

    def test_a_profile_without_a_form_has_none(self):
        p = wp.parse_profile(fake())
        self.assertIsNone(p.form)
        self.assertIsNone(p.form_paths("x"))

    def test_a_bad_form_is_rejected(self):
        for form in ("s.md", {"structure": "s.md"}, {"structure": "s.md", "poem": 3},
                     {"structure": "s.md", "poem": "work/{slug}.md", "x": "y"}):
            with self.subTest(form), self.assertRaises(wp.ProfileError) as cm:
                wp.parse_profile(fake(form=form))
            self.assertIn("'form' must be an object with only 'structure' and 'poem' paths", str(cm.exception))

    def test_a_form_path_must_be_a_listed_file(self):
        with self.assertRaises(wp.ProfileError) as cm:
            wp.parse_profile(fake(form={"structure": "nope.md", "poem": "work/{slug}.md"}))
        self.assertIn("'form' structure path 'nope.md' is not listed in 'files'", str(cm.exception))

    def test_the_other_profiles_have_no_form(self):
        for name in ("shortstory", "novel", "screenplay"):
            self.assertIsNone(wp.load_profile(name).form, name)


class PoemProfile(unittest.TestCase):
    def setUp(self):
        self.p = wp.load_profile("poem")
        self.p.set_premise({"titled": "no"})

    def test_file_shape(self):
        self.assertEqual([path for path, _ in self.p.expected_files("counting")], ["structure.md", "work/counting.md"])

    def test_settings(self):
        self.assertEqual(self.p.form, {"structure": "structure.md", "poem": "work/{slug}.md"})
        self.assertEqual(self.p.publish_style, "poem")
        self.assertEqual(self.p.lint_format, "prose")
        self.assertIs(self.p.title_page, False)
        self.assertEqual(self.p.premise_keys, {"titled": {"type": "bool"}})

    def test_functions(self):
        f = self.p.functions
        self.assertEqual(f["structure"]["required_when_realized"], ["Form", "Lines", "Stanzas"])
        self.assertEqual(f["structure"]["fields"], ["Rhyme", "Meter"])
        self.assertFalse(f["structure"]["prose"])
        self.assertTrue(f["poem"]["prose"])
        self.assertEqual(f["poem"]["fields"], ["Subject", "Speaker", "Tone", "Turn", "Ending", "Must include",
                                               "Must avoid", "Must keep"])

    def test_questions(self):
        self.assertEqual({q.id for q in self.p.questions if q.required}, {"subject", "form", "tone", "audience", "length"})
        self.assertEqual({q.id for q in self.p.questions if not q.required},
                         {"speaker", "occasion", "rhyme", "images", "avoid", "titled", "epigraph", "dedication", "keep"})

    def test_every_premise_key_has_a_question(self):
        self.assertEqual({self.p.question_key(q.id) for q in self.p.questions} - {None}, set(self.p.premise_keys))

    def test_titled_is_yes_or_no_and_defaults_to_no(self):
        self.assertEqual(self.p.resolve_options({})[0], {"titled": False})
        self.assertEqual(self.p.resolve_options({"titled": "yes"})[0], {"titled": True})
        self.assertEqual(self.p.resolve_options({"titled": "maybe"})[1][0][0], "titled")


class PoemContent(unittest.TestCase):
    def read(self, name):
        with open(os.path.join(PROFILE_DIR, name), encoding="utf-8") as fh:
            return fh.read()

    def test_forms_md_covers_every_catalog_form(self):
        text = self.read("forms.md")
        for name in wrist_verse.list_catalog(os.path.join(PROFILE_DIR, "forms")):
            self.assertIn(f"## {name}\n", text, name)

    def test_the_questions_name_every_catalog_form(self):
        text = self.read("questions.md")
        for name in wrist_verse.list_catalog(os.path.join(PROFILE_DIR, "forms")):
            self.assertIn(name, text, name)

    def test_quality_md_has_its_three_parts_and_the_prompt_rules(self):
        text = self.read("quality.md")
        for heading in ("## Clichés and stock moves", "## Marks of low quality", "## Judgment checklist"):
            self.assertIn(heading, text)
        for phrase in ("At most one simile", "Delete the last line", "unjustifiable", "Must keep:", "moment"):
            self.assertIn(phrase, text, phrase)
        self.assertGreaterEqual(text.count("- [ ] "), 10)

    def test_every_lint_pattern_matches_its_positive_and_not_its_negative(self):
        items = wp.load_profile("poem").lint_items()
        self.assertGreaterEqual(len(items), 15)
        for item in items:
            with self.subTest(item["id"]):
                rx = re.compile(item["pattern"], re.IGNORECASE)
                self.assertTrue(rx.search(item["positive"]), "positive sample does not match")
                self.assertFalse(rx.search(item["negative"]), "negative sample matches")

    def test_the_banned_words_are_all_linted(self):
        items = wp.load_profile("poem").lint_items()
        for word in ("starlight", "threshold", "void", "cathedral", "hymn", "cradle", "unfold", "becoming", "luminous",
                     "tapestry", "whisper", "echo", "shatter", "dance", "ache", "infinite", "sacred", "silence", "moment"):
            self.assertTrue(any(re.search(i["pattern"], word, re.I) for i in items), word)
