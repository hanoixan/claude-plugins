import json
import os
import shutil
import subprocess
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


READER = os.path.normpath(os.path.join(HERE, "..", "skills", "wrist", "publish", "screenplay", "fountain.lua"))
HAVE_PANDOC = shutil.which("pandoc") is not None


def read(text):
    """The reader's top-level blocks as pandoc JSON."""
    proc = subprocess.run(["pandoc", "--from", READER, "-t", "json"], input=text, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)["blocks"]


def kind(block):
    return block["c"][0][1][0] if block["t"] == "Div" else block["t"]


def plain(blocks):
    """The text of blocks, flattened, for assertions about content."""
    out = []

    def walk(node):
        if isinstance(node, dict):
            if node.get("t") == "Str":
                out.append(node["c"])
            elif node.get("t") in ("Space", "SoftBreak", "LineBreak"):
                out.append(" ")
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(blocks)
    return "".join(out)


@unittest.skipUnless(HAVE_PANDOC, "pandoc is not installed")
class LuaReader(unittest.TestCase):
    def test_review_focus_the_reader_follows_every_shared_case(self):
        for case in CASES:
            with self.subTest(case["name"]):
                self.assertEqual([kind(b) for b in read(case["text"])], case["kinds"])

    def test_the_reader_and_the_classifier_agree_on_every_case(self):
        for case in CASES:
            with self.subTest(case["name"]):
                self.assertEqual([kind(b) for b in read(case["text"])], wrist_lint.elements(case["text"]))

    def test_emphasis_is_kept(self):
        blocks = read("She holds a *clipboard* and a **pen**.\n")
        self.assertEqual(kind(blocks[0]), "action")
        flat = json.dumps(blocks)
        self.assertIn('"t": "Emph"', flat)
        self.assertIn('"t": "Strong"', flat)

    def test_text_content_survives(self):
        text = plain(read("INT. FERRY DECK - NIGHT\n\nMARIT\n(quietly)\nTwenty-three.\n"))
        for needle in ("INT. FERRY DECK - NIGHT", "MARIT", "(quietly)", "Twenty-three."):
            self.assertIn(needle, text)

    def test_a_forced_heading_loses_its_dot_and_a_scene_number_is_dropped(self):
        text = plain(read(".THE BEACH\n\nWaves.\n\nINT. HOUSE - DAY #12#\n\nGo.\n"))
        self.assertIn("THE BEACH", text)
        self.assertNotIn(".THE", text)
        self.assertNotIn("#12#", text)

    def test_a_forced_character_loses_its_at_sign(self):
        text = plain(read("@McCLOUD\nHi.\n"))
        self.assertIn("McCLOUD", text)
        self.assertNotIn("@", text)

    def test_a_line_that_looks_like_a_list_is_kept_literally(self):
        text = plain(read("1. The house\n"))
        self.assertIn("1. The house", text)

    def test_special_characters_pass_through(self):
        text = plain(read('MARIT\nA & B #1 — "Q" café $5 @mara <Ann>\n'))
        for needle in ("A & B #1", "café", "$5", "@mara"):
            self.assertIn(needle, text)

    def test_the_act_marker_keeps_its_whole_label(self):
        block = read("@@ACT TWO@@\n\nINT. A - DAY\n\nText.\n")[0]
        self.assertEqual(kind(block), "act-marker")
        self.assertEqual(plain([block]).strip(), "ACT TWO")

    def test_review_focus_line_breaks_in_action_and_dialogue_are_kept(self):
        """Fountain takes every carriage return as intent (fountain.io, Line Breaks)."""
        for text in ("Line one.\nLine two.\n", "MARIT\nRow, row,\nrow your boat.\n"):
            with self.subTest(text=text):
                self.assertIn('"LineBreak"', json.dumps(read(text)))

    def test_a_single_line_has_no_line_break(self):
        self.assertNotIn('"LineBreak"', json.dumps(read("One line only.\n")))

    def test_a_long_script_reads_in_one_pass(self):
        script = "\n".join(f"INT. ROOM {i} - DAY\n\nMARIT\nLine {i}.\n" for i in range(100))
        self.assertEqual(len(read(script)), 300)


if __name__ == "__main__":
    unittest.main()
