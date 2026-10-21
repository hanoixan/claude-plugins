"""Tests for agentropy-guard's skills, agents, report template and the page check."""
import os
import re
import subprocess
import sys
import unittest

from test_guard import PLUGIN, SCRIPT, Case, g

SKILLS = os.path.join(PLUGIN, "skills")
AGENTS = os.path.join(PLUGIN, "agents")
USER_ONLY = ("scan", "queue", "findings")
MODEL = ("erosion-check", "educate", "ledger-update", "arch-report")


def read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as fh:
        return fh.read()


def all_docs():
    out = []
    for folder in (SKILLS, AGENTS):
        for base, _, files in os.walk(folder):
            out += [read(base, f) for f in files if f.endswith(".md")]
    return "\n".join(out)


class Skills(unittest.TestCase):
    def test_each_skill_has_front_matter_with_its_name(self):
        for name in USER_ONLY + MODEL:
            text = read(SKILLS, name, "SKILL.md")
            self.assertTrue(text.startswith(f"---\nname: {name}\ndescription: "), name)
            self.assertEqual("\ndisable-model-invocation: true\n" in text.split("\n---\n", 1)[0] + "\n",
                             name in USER_ONLY, name)

    def test_every_command_is_documented(self):
        docs = all_docs()
        for name in g.REGISTRY:
            self.assertIn(f"GUARD {name}", docs, name)

    def test_the_skills_the_hooks_name_exist(self):
        for name in ("erosion-check", "educate", "arch-report", "scan"):
            self.assertTrue(os.path.exists(os.path.join(SKILLS, name, "SKILL.md")), name)
        self.assertTrue(os.path.exists(os.path.join(AGENTS, "erosion-reviewer.md")))

    def test_each_agent_has_front_matter(self):
        for name in ("architecture-scout", "erosion-reviewer"):
            text = read(AGENTS, f"{name}.md")
            head = text.split("\n---\n", 1)[0]
            self.assertTrue(head.startswith(f"---\nname: {name}\ndescription: "), name)
            self.assertIn("\ntools: ", head)

    def test_the_warning_offers_the_four_choices(self):
        text = read(SKILLS, "erosion-check", "SKILL.md")
        for words in ("Fix now", "Note it, later", "Accept this", "False positive", "GUARD finding decide"):
            self.assertIn(words, text)

    def test_the_nudge_is_exempted_through_question_refiner(self):
        text = read(SKILLS, "educate", "SKILL.md")
        self.assertIn('reason "architecture note"', text)
        self.assertIn("at most one", text)


class Template(unittest.TestCase):
    def setUp(self):
        self.text = read(SKILLS, "arch-report", "template.html")

    def test_it_is_print_ready_and_themed(self):
        self.assertIn("@page { size: Letter; margin: 0.6in; }", self.text)
        self.assertIn("prefers-color-scheme: dark", self.text)
        for slot in ("TITLE", "WHY", "BLOCK_DIAGRAM", "SEQUENCE_SECTION", "CONSEQUENCES", "ORIGIN", "EVIDENCE",
                     "COUNTERMOVE_SECTION", "GENERATED"):
            self.assertIn("{{" + slot + "}}", self.text)

    def test_it_makes_no_external_requests(self):
        self.assertIsNone(re.search(r"""(?:src|href)\s*=\s*["']?\s*(?:https?:)?//""", self.text))
        self.assertNotIn("<script", self.text)
        self.assertNotIn("@import", self.text)

    def test_the_diagram_guide_sets_the_conventions(self):
        guide = read(SKILLS, "arch-report", "diagram-guide.md")
        for words in ("dashed", "8 participants", "15 messages", "caption", "class=\"accent\""):
            self.assertIn(words, guide)


class Pages(Case):
    def test_pages_are_counted_from_the_pdf(self):
        pdf = b"<< /Type /Pages /Count 2 >> << /Type /Page >> << /Type/Page /Parent 1 0 R >>"
        self.assertEqual(g.count_pdf_pages(pdf), 2)

    def test_without_chrome_the_check_is_skipped(self):
        path = os.path.join(self.root, "r.html")
        self.write("r.html", "<html></html>")
        env = {**os.environ, "PATH": os.path.join(self.home, "empty")}
        result = subprocess.run([sys.executable, SCRIPT, "pages", path], capture_output=True, text=True, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("skipped: no headless Chrome or Chromium", result.stdout)


if __name__ == "__main__":
    unittest.main()
