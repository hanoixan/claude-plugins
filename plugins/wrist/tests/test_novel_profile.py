import os
import re
import unittest

from support import SKILL

import wrist_profile as wp


class NovelProfile(unittest.TestCase):
    def setUp(self):
        self.p = wp.load_profile("novel")
        self.p.set_premise({"chapters": "28", "forward": "yes", "prologue": "no", "afterward": "yes", "index": "no"})

    def paths(self):
        return [path for path, _ in self.p.expected_files("salt-road")]

    def test_file_shape_follows_the_listing_order(self):
        paths = self.paths()
        self.assertEqual(paths[:5], ["synopsis.md", "outline.md", "character.md", "misc.md", "work/forward.md"])
        self.assertEqual(paths[5], "work/chapter-01.md")
        self.assertEqual(paths[-2:], ["work/chapter-28.md", "work/afterward.md"])
        self.assertEqual(len(paths), 4 + 1 + 28 + 1)       # four registries, forward, 28 chapters, afterward
        self.assertNotIn("work/prologue.md", paths)
        self.assertNotIn("work/index.md", paths)

    def test_the_premise_keys_are_declared(self):
        keys = self.p.premise_keys
        self.assertEqual(keys["chapters"], {"type": "int", "min": 1, "max": 200, "required": True})
        for name in ("forward", "prologue", "afterward", "index"):
            self.assertEqual(keys[name]["type"], "bool")

    def test_a_novel_has_a_title_page(self):
        self.assertIs(self.p.title_page, True)

    def test_chapters_are_a_sequence_with_established_and_a_heading(self):
        spec = self.p.functions["chapter"]
        self.assertTrue(spec["sequence"])
        self.assertEqual(spec["required_when_realized"], ["Established"])
        self.assertEqual(spec["heading_field"], "Heading")
        self.assertEqual(spec["children"]["scene"], ["Purpose", "Length", "Must include", "Must avoid"])

    def test_the_prose_functions(self):
        self.assertEqual(sorted(n for n, s in self.p.functions.items() if s["prose"]),
                         ["afterward", "chapter", "forward", "index", "prologue"])

    def test_the_registries(self):
        self.assertEqual(self.p.functions["characters"]["children"]["character"], ["Wants", "Flaw", "Voice", "Arc"])
        self.assertIn("timeline", self.p.functions["misc"]["children"])

    def test_relations_include_continues(self):
        for word in ("appears", "mentions", "sets up", "pays off", "realizes", "continues"):
            self.assertIn(word, self.p.relations)

    def test_questions(self):
        required = {q.id for q in self.p.questions if q.required}
        self.assertEqual(required, {"genre", "premise", "ending", "tone", "audience", "length", "chapters", "viewpoint"})
        deferrable = {q.id for q in self.p.questions if not q.required}
        self.assertEqual(deferrable, {"subgenre", "setting", "worldrules", "themes", "comps", "series", "characters",
                                      "events", "fixed", "structure", "avoid", "forward", "prologue", "afterward",
                                      "index"})

    def test_every_premise_key_has_a_question(self):
        ids = {q.id for q in self.p.questions}
        self.assertLessEqual(set(self.p.premise_keys), ids)


class NovelReferenceContent(unittest.TestCase):
    def read(self, name):
        with open(os.path.join(SKILL, "profiles", "novel", name), encoding="utf-8") as fh:
            return fh.read()

    def test_structures(self):
        text = self.read("structures.md")
        for name in ("Three-act", "Save the Cat!", "Hero's Journey", "Seven-Point", "Five-act", "Fichtean curve",
                     "Story Circle"):
            self.assertIn(name, text)
        sections = [s for s in text.split("\n## ")[1:]]
        for section in sections:
            title = section.split("\n")[0]
            if title.startswith("Genre"):
                continue
            self.assertIn("**Best for:**", section, title)
            self.assertIn("**Spread across the chapters:**", section, title)

    def test_the_genre_table_names_the_genres(self):
        text = self.read("structures.md")
        for genre in ("mystery", "romance", "thriller", "fantasy", "science fiction", "literary", "young adult",
                      "historical", "horror"):
            self.assertIn(genre, text.lower())

    def test_quality_has_its_parts(self):
        text = self.read("quality.md")
        for heading in ("## Clichés and stock moves", "## Marks of low quality", "## Judgment checklist"):
            self.assertIn(heading, text)
        self.assertGreaterEqual(text.count("- [ ] "), 14)
        for phrase in ("midpoint", "Established", "subplot"):
            self.assertIn(phrase, text)

    def test_every_lint_pattern_matches_its_positive_and_not_its_negative(self):
        items = wp.load_profile("novel").lint_items()
        self.assertGreaterEqual(len(items), 29)
        ids = [i["id"] for i in items]
        self.assertEqual(len(ids), len(set(ids)))
        for item in items:
            with self.subTest(item["id"]):
                rx = re.compile(item["pattern"], re.IGNORECASE)
                self.assertTrue(rx.search(item["positive"]), "positive sample does not match")
                self.assertFalse(rx.search(item["negative"]), "negative sample matches")

    def test_the_novel_keeps_the_short_story_patterns_and_adds_its_own(self):
        short = {i["id"] for i in wp.load_profile("shortstory").lint_items()}
        novel = {i["id"] for i in wp.load_profile("novel").lint_items()}
        self.assertLessEqual(short, novel)
        self.assertGreaterEqual(len(novel - short), 8)


if __name__ == "__main__":
    unittest.main()
