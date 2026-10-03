import os
import unittest

from support import MV, OUTLINE, PREMISE, STORY, SYNOPSIS, TreeCase

BACKLINK = "- **Referred by:** [outline](./outline.md.wrist.md)\n"


class FixBacklinks(TreeCase):
    def test_write_restores_a_deleted_backlink(self):
        self.replace(SYNOPSIS, BACKLINK, "")
        self.assertEqual(self.check()[0], 1)
        self.run_wrist("fix-backlinks", "wrist", "--write")
        code, out = self.check()
        self.assertEqual(code, 0, out)

    def test_dry_run_changes_nothing(self):
        self.replace(SYNOPSIS, BACKLINK, "")
        _, out = self.run_wrist("fix-backlinks", "wrist")
        self.assertIn("dry run", out)
        self.assertEqual(self.check()[0], 1)

    def test_nothing_to_fix(self):
        _, out = self.run_wrist("fix-backlinks", "wrist")
        self.assertIn("All backlinks present.", out)


class Move(TreeCase):
    def moved_check(self):
        code, out = self.check()
        self.assertNotIn("link target does not exist", out)
        self.assertNotIn("missing backlink", out)
        return out

    def test_moving_a_file_rewrites_every_link(self):
        code, out = self.run_script(MV, "wrist", STORY, "wrist/work/lamp-two.md.wrist.md")
        self.assertEqual(code, 0, out)
        self.assertTrue(os.path.exists(self.path("wrist/work/lamp-two.md.wrist.md")))
        self.moved_check()

    def test_moving_a_directory_rewrites_every_link(self):
        code, out = self.run_script(MV, "wrist", "wrist/work", "wrist/pieces")
        self.assertEqual(code, 0, out)
        self.moved_check()

    def test_links_in_the_premise_are_rewritten(self):
        self.append(PREMISE, "\nOutline: [outline](./outline.md.wrist.md).\n")
        self.run_script(MV, "wrist", OUTLINE, "wrist/plan/outline.md.wrist.md")
        self.assertIn("(./plan/outline.md.wrist.md)", self.read(PREMISE))

    def test_dry_run_moves_nothing(self):
        self.run_script(MV, "wrist", STORY, "wrist/work/lamp-two.md.wrist.md", "--dry-run")
        self.assertTrue(os.path.exists(self.path(STORY)))

    def test_links_inside_fences_are_left_alone(self):
        self.append(OUTLINE, "\n```text\n[x](./synopsis.md.wrist.md)\n```\n")
        self.run_script(MV, "wrist", SYNOPSIS, "wrist/start/synopsis.md.wrist.md")
        self.assertIn("```text\n[x](./synopsis.md.wrist.md)\n```", self.read(OUTLINE))


if __name__ == "__main__":
    unittest.main()
