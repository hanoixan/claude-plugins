"""skel's text after the interview loop moved to question-refiner.

Run: python3 -m unittest discover -s plugins/skel/tests
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

SKILL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "skills", "skel")
CHECK = os.path.join(SKILL, "scripts", "skel_check.py")
EXAMPLE = os.path.join(SKILL, "assets", "examples", "undo-system", "skel")


def read(*parts):
    with open(os.path.join(SKILL, *parts), encoding="utf-8") as fh:
        return fh.read()


class Docs(unittest.TestCase):
    def test_the_system_template_has_principles(self):
        self.assertIn("## Principles", read("assets", "templates", "SYSTEM.md"))

    def test_skel_no_longer_ships_the_loop(self):
        for parts in (("scripts", "interview.py"), ("references", "interviewing.md"),
                      ("references", "interview-tags.md")):
            self.assertFalse(os.path.exists(os.path.join(SKILL, *parts)), parts)

    def test_no_text_points_at_the_old_loop(self):
        for folder, _, files in os.walk(SKILL):
            for name in files:
                if name.endswith(".md"):
                    with open(os.path.join(folder, name), encoding="utf-8") as fh:
                        text = fh.read()
                    for old in ("interview.py", "interviewing.md", "interview-tags.md", "interview round"):
                        self.assertNotIn(old, text, os.path.join(folder, name))

    def test_questions_go_through_question_refiner_or_directly(self):
        text = read("SKILL.md")
        self.assertIn("- **Questions:**", text)
        self.assertIn("question-refiner skill when it is available", text)
        self.assertIn("Otherwise ask directly", text)
        for name in ("implementing.md", "abstract-systems.md"):
            self.assertIn("Questions", read("references", name))

    def test_old_files_point_to_question_refiner(self):
        self.assertIn(".interview-moved.md", read("SKILL.md"))

    def test_the_templates_say_nothing_of_interviews(self):
        folder = os.path.join(SKILL, "assets", "templates")
        for name in os.listdir(folder):
            with open(os.path.join(folder, name), encoding="utf-8") as fh:
                self.assertNotIn("interview", fh.read().lower(), name)


class Coexistence(unittest.TestCase):
    def test_check_ignores_the_old_interview_files(self):
        work = tempfile.mkdtemp(prefix="skel-docs-")
        self.addCleanup(shutil.rmtree, work, ignore_errors=True)
        skel = os.path.join(work, "skel")
        shutil.copytree(EXAMPLE, skel)
        for name in (".interviews.md", ".interview-weights.md", ".interview-round.md", ".interview-moved.md"):
            with open(os.path.join(skel, name), "w", encoding="utf-8") as fh:
                fh.write("# not a stand-in\n")
        result = subprocess.run([sys.executable, CHECK, "check", skel], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
