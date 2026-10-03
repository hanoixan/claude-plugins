import os
import unittest

from support import (N_CHAPTER1, N_CHAPTER2, N_CHAPTER3, N_OUTLINE, N_PREMISE, NovelCase)


class SaltRoadChecks(NovelCase):
    def test_the_example_checks_clean(self):
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("8 stand-ins", out)
        self.assertIn("0 errors, 0 warnings", out)

    def test_every_gate_is_open(self):
        for phase in ("generation", "realization", "publishing"):
            code, out = self.run_wrist("gate", "wrist", phase)
            self.assertEqual(code, 0, out)

    def test_every_file_is_realized(self):
        code, out = self.run_wrist("status", "wrist")
        self.assertIn("Realized (8):", out)

    def test_order_follows_the_profile(self):
        _, out = self.run_wrist("order", "wrist")
        names = [l.split()[1] for l in out.splitlines() if l[:1].isdigit()]
        self.assertEqual(names, ["synopsis.md", "outline.md", "character.md", "misc.md", "work/forward.md",
                                 "work/chapter-1.md", "work/chapter-2.md", "work/chapter-3.md"])

    def test_lint_is_clean(self):
        _, out = self.run_wrist("lint", "wrist")
        self.assertIn("0 hits in 0 files", out)


class SaltRoadFileSet(NovelCase):
    def test_a_fourth_chapter_needs_its_stand_in(self):
        self.replace(N_PREMISE, "chapters: 3", "chapters: 4")
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("required stand-in missing: wrist/work/chapter-4.md.wrist.md", out)

    def test_dropping_the_forward_leaves_its_stand_in_outside_the_shape(self):
        self.replace(N_PREMISE, "forward: yes", "forward: no")
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("outside the novel shape", out)

    def test_a_prologue_must_have_its_stand_in(self):
        self.replace(N_PREMISE, "prologue: no", "prologue: yes")
        code, out = self.check()
        self.assertIn("required stand-in missing: wrist/work/prologue.md.wrist.md", out)

    def test_a_missing_chapters_key_is_a_clear_error(self):
        self.replace(N_PREMISE, "chapters: 3\n", "")
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("`chapters:` is required (a whole number from 1 to 200)", out)

    def test_the_chapters_question_is_answered_by_the_front_matter(self):
        code, out = self.check()
        self.assertNotIn("question 'chapters'", out)
        self.assertNotIn("question 'forward'", out)


class SaltRoadContinuity(NovelCase):
    def test_stamp_refuses_a_chapter_with_no_established_text(self):
        self.replace(N_CHAPTER2, "- **Established:** Brannock", "- **Notes:** Brannock")
        code, out = self.run_wrist("stamp", "wrist", "work/chapter-2.md")
        self.assertEqual(code, 1, out)
        self.assertIn("no `Established:` text", out)

    def test_the_gate_blocks_a_chapter_whose_established_was_removed(self):
        text = self.read(N_CHAPTER3)
        kept = "\n".join(l for l in text.split("\n") if not l.startswith("- **Established:**"))
        self.write(N_CHAPTER3, kept)
        code, out = self.run_wrist("gate", "wrist", "publishing")
        self.assertEqual(code, 1, out)
        self.assertIn("work/chapter-3.md: its stand-in has no `Established:` text", out)

    def test_a_chapter_must_continue_the_one_before(self):
        self.replace(N_CHAPTER3, "(continues)", "(mentions)")
        code, out = self.check()
        self.assertIn("no `Depends on:` link to work/chapter-2.md's stand-in with the relation `continues`", out)

    def test_a_chapter_heading_that_drifts_blocks_publishing(self):
        self.write("work/chapter-1.md", self.read("work/chapter-1.md").replace("# 1. The Load", "# One: The Load"))
        self.run_wrist("stamp", "wrist", "work/chapter-1.md")
        code, out = self.run_wrist("gate", "wrist", "publishing")
        self.assertEqual(code, 1, out)
        self.assertIn("starts with '# One: The Load' but its stand-in's `Heading:` says '# 1. The Load'", out)

    def test_editing_a_chapter_after_stamping_blocks_publishing(self):
        self.write("work/chapter-2.md", self.read("work/chapter-2.md") + "\nA stray line.\n")
        code, out = self.run_wrist("gate", "wrist", "publishing")
        self.assertIn("work/chapter-2.md is edited", out)


if __name__ == "__main__":
    unittest.main()
