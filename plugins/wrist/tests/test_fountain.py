import json
import os
import unittest

from support import HERE     # first: it puts the scripts folder on sys.path

import wrist_lint

with open(os.path.join(HERE, "fountain_cases.json"), encoding="utf-8") as fh:
    CASES = json.load(fh)


class SharedCases(unittest.TestCase):
    def test_the_python_classifier_follows_every_shared_case(self):
        for case in CASES:
            with self.subTest(case["name"]):
                self.assertEqual(wrist_lint.elements(case["text"]), case["kinds"])


class LineKinds(unittest.TestCase):
    def kinds(self, text):
        return [(n, k) for n, k, _ in wrist_lint.classify_fountain(text)]

    def test_every_line_gets_a_kind_with_its_own_number(self):
        text = "INT. A - DAY\n\nMARIT\n(softly)\nHi.\n\nCUT TO:\n"
        self.assertEqual(self.kinds(text), [(1, "heading"), (2, "blank"), (3, "character"), (4, "parenthetical"),
                                            (5, "dialogue"), (6, "blank"), (7, "transition"), (8, "blank")])

    def test_comments_are_blanked_but_every_line_keeps_its_number(self):
        text = "[[a\nb]]\n\nWe see it.\n"
        kinds = self.kinds(text)
        self.assertEqual(kinds[3], (4, "action"))
        self.assertEqual(wrist_lint.mask_comments(text).count("\n"), text.count("\n"))

    def test_masked_text_does_not_leak_into_the_line(self):
        _, kind, line = wrist_lint.classify_fountain("Text [[secret]] here.\n")[0]
        self.assertNotIn("secret", line)
        self.assertEqual(kind, "action")

    def test_strip_comments_removes_what_the_reader_removes(self):
        self.assertEqual(wrist_lint.strip_comments("a /* x */ b [[y]] c"), "a  b  c")


class FountainLint(unittest.TestCase):
    ITEMS = [
        {"id": "we-see", "pattern": r"\bwe see\b", "label": "l", "note": "n", "scope": "action"},
        {"id": "as-you-know", "pattern": r"\bas you know\b", "label": "l", "note": "n", "scope": "dialogue"},
        {"id": "anywhere", "pattern": r"\bfog\b", "label": "l", "note": "n", "scope": "anywhere"},
    ]

    def hits(self, text):
        return [(h["line"], h["id"]) for h in wrist_lint.lint_text(text, self.ITEMS, "fountain")]

    def test_review_focus_an_action_pattern_ignores_dialogue(self):
        self.assertEqual(self.hits("MARIT\nWe see it, as you know.\n"), [(2, "as-you-know")])

    def test_review_focus_a_dialogue_pattern_ignores_action(self):
        self.assertEqual(self.hits("As you know, we see it.\n"), [(1, "we-see")])

    def test_a_dialogue_pattern_reaches_parentheticals(self):
        self.assertEqual(self.hits("MARIT\n(as you know)\nHi.\n"), [(2, "as-you-know")])

    def test_an_anywhere_pattern_reaches_headings_dialogue_and_transitions(self):
        text = "EXT. FOG BANK - DAY\n\nMARIT\nThe fog.\n\nFOG TO:\n"
        self.assertEqual(self.hits(text), [(1, "anywhere"), (4, "anywhere"), (6, "anywhere")])

    def test_review_focus_hit_line_numbers_survive_a_multi_line_note(self):
        self.assertEqual(self.hits("[[a\nb]]\n\nWe see it.\n"), [(4, "we-see")])

    def test_text_inside_notes_and_boneyard_is_not_linted(self):
        self.assertEqual(self.hits("Quiet. [[we see this]]\n\n/* we see that */\n"), [])

    def test_prose_format_is_unchanged(self):
        items = [{"id": "x", "pattern": "dark", "label": "l", "note": "n", "scope": "narration"}]
        self.assertEqual(len(wrist_lint.lint_text("It was dark.", items)), 1)
        self.assertEqual(wrist_lint.lint_text('"dark," he said.', items), [])


if __name__ == "__main__":
    unittest.main()
