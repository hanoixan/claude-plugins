import re
import unittest

from support import TreeCase     # first: it puts the scripts folder on sys.path

import wrist_lint
import wrist_profile

STORY_REAL = "work/the-lamp.md"


class EveryPattern(unittest.TestCase):
    def test_each_pattern_matches_its_positive_and_not_its_negative(self):
        items = wrist_profile.load_profile("shortstory").lint_items()
        self.assertGreaterEqual(len(items), 20)
        ids = [i["id"] for i in items]
        self.assertEqual(len(ids), len(set(ids)))
        for item in items:
            with self.subTest(item["id"]):
                rx = re.compile(item["pattern"], re.IGNORECASE)
                self.assertTrue(rx.search(item["positive"]), "positive sample does not match")
                self.assertFalse(rx.search(item["negative"]), "negative sample matches")


class LintText(unittest.TestCase):
    ITEMS = [
        {"id": "narr", "pattern": "dark and stormy", "label": "l1", "note": "n1", "scope": "narration"},
        {"id": "any", "pattern": "shiver", "label": "l2", "note": "n2", "scope": "anywhere"},
    ]

    def test_narration_hits_are_reported_with_their_line(self):
        hits = wrist_lint.lint_text("one\nIt was a dark and stormy night.\n", self.ITEMS)
        self.assertEqual([(h["line"], h["id"], h["text"]) for h in hits], [(2, "narr", "dark and stormy")])

    def test_narration_scope_ignores_quoted_dialogue(self):
        self.assertEqual(wrist_lint.lint_text('"A dark and stormy night," he said.', self.ITEMS), [])

    def test_curly_quotes_count_as_dialogue(self):
        self.assertEqual(wrist_lint.lint_text("“A dark and stormy night,” he said.", self.ITEMS), [])

    def test_anywhere_scope_flags_dialogue_too(self):
        hits = wrist_lint.lint_text('"I shiver," he said.', self.ITEMS)
        self.assertEqual([h["id"] for h in hits], ["any"])

    def test_text_after_the_closing_quote_is_narration_again(self):
        hits = wrist_lint.lint_text('"No," he said. A dark and stormy night.', self.ITEMS)
        self.assertEqual([h["id"] for h in hits], ["narr"])

    def test_matching_is_case_insensitive(self):
        self.assertEqual(len(wrist_lint.lint_text("DARK AND STORMY", self.ITEMS)), 1)


class LintCommand(TreeCase):
    def lint(self):
        return self.run_wrist("lint", "wrist")

    def test_the_example_has_no_hits(self):
        code, out = self.lint()
        self.assertEqual(code, 0, out)
        self.assertIn("0 hits in 0 files", out)

    def test_a_cliche_in_narration_is_reported_with_file_and_line(self):
        self.replace(STORY_REAL, "The street went on outside.",
                     "A shiver ran down her spine. The street went on outside.")
        code, out = self.lint()
        self.assertEqual(code, 0, out)
        self.assertRegex(out, r"work/the-lamp\.md:\d+: \[shiver-spine\]")
        self.assertIn("1 hits in 1 files", out)

    def test_the_same_phrase_in_dialogue_is_not_reported(self):
        self.replace(STORY_REAL, '"Leave it on the bench," she said.',
                     '"A shiver ran down my spine," she said.')
        code, out = self.lint()
        self.assertIn("0 hits", out)

    def test_an_anywhere_pattern_is_reported_inside_dialogue(self):
        self.replace(STORY_REAL, '"Nothing."', '"It was a dark and stormy night."')
        code, out = self.lint()
        self.assertIn("[dark-stormy]", out)

    def test_lint_never_fails_the_run(self):
        self.replace(STORY_REAL, "Tomas knocked anyway.", "Suddenly Tomas knocked anyway.")
        code, out = self.lint()
        self.assertEqual(code, 0, out)

    def test_only_prose_files_are_linted(self):
        self.replace("synopsis.md", "takes in", "suddenly takes in")
        code, out = self.lint()
        self.assertIn("0 hits", out)

    def test_pointer_to_the_judgment_checklist(self):
        _, out = self.lint()
        self.assertIn("quality.md", out)


class LintItemValidation(unittest.TestCase):
    def load(self, items):
        import json
        import os
        import shutil
        import tempfile
        d = tempfile.mkdtemp(prefix="wrist-lint-")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        prof = os.path.join(d, "t")
        os.makedirs(prof)
        data = {"name": "t", "files": [{"path": "a.md", "function": "a", "order": 1}],
                "functions": {"a": {"heading": "a"}}, "relations": [], "limits": {"max_prose_words": 5}}
        with open(os.path.join(prof, "profile.json"), "w") as fh:
            json.dump(data, fh)
        with open(os.path.join(prof, "lint.json"), "w") as fh:
            json.dump({"items": items}, fh)
        return wrist_profile.load_profile("t", d).lint_items()

    GOOD = {"id": "x", "pattern": "a", "label": "l", "note": "n", "scope": "anywhere",
            "positive": "a", "negative": "b"}

    def test_a_good_item_loads(self):
        self.assertEqual(len(self.load([self.GOOD])), 1)

    def test_a_bad_pattern_is_rejected(self):
        with self.assertRaises(wrist_profile.ProfileError) as cm:
            self.load([dict(self.GOOD, pattern="(")])
        self.assertIn("pattern", str(cm.exception))

    def test_an_unknown_scope_is_rejected(self):
        with self.assertRaises(wrist_profile.ProfileError):
            self.load([dict(self.GOOD, scope="dialogue")])

    def test_a_missing_key_is_rejected(self):
        bad = dict(self.GOOD)
        del bad["note"]
        with self.assertRaises(wrist_profile.ProfileError):
            self.load([bad])

    def test_no_lint_file_means_no_items(self):
        self.assertEqual(wrist_profile.parse_profile(
            {"name": "t", "files": [{"path": "a.md", "function": "a", "order": 1}],
             "functions": {"a": {"heading": "a"}}, "relations": [], "limits": {"max_prose_words": 5}}
        ).lint_items(), [])


if __name__ == "__main__":
    unittest.main()
