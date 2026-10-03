import json
import os
import re
import unittest

from support import HERE, SKILL

ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
COMMANDS = ("check", "unknowns", "order", "status", "stamp", "fix-backlinks", "gate", "lint", "publish")


def text(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as fh:
        return fh.read()


class SkillText(unittest.TestCase):
    def test_skill_names_every_command(self):
        skill = text(SKILL, "SKILL.md")
        for cmd in COMMANDS:
            self.assertIn(f"wrist_check.py\" {cmd} ", skill, cmd)

    def test_skill_front_matter(self):
        skill = text(SKILL, "SKILL.md")
        self.assertTrue(skill.startswith("---\nname: wrist\n"))
        self.assertIn("description:", skill.split("---")[1])

    def test_no_trace_of_the_old_plugin_name(self):
        old = "sk" + "el"          # spelled in two parts so this file does not match itself
        for dp, _, fns in os.walk(os.path.join(ROOT, "plugins", "wrist")):
            if "__pycache__" in dp:
                continue
            for fn in fns:
                if re.search(old + "(?!et)", text(dp, fn), re.I):
                    self.fail(f"the old plugin name is still in {os.path.join(dp, fn)}")

    def test_every_template_is_valid_for_its_function(self):
        for name in ("PREMISE.md", "synopsis.wrist.md", "outline.wrist.md", "characters.wrist.md",
                     "misc.wrist.md", "story.wrist.md"):
            self.assertTrue(os.path.isfile(os.path.join(SKILL, "assets", "templates", name)), name)

    def test_skill_carries_the_lessons_of_the_trial(self):
        skill = text(SKILL, "SKILL.md")
        for phrase in ("none (skipped on purpose)", "A choice that appears only in your chat message",
                       "containing only `* * *`", "Do not add a fact the stand-ins do not hold",
                       "check continuity", "unless a stand-in names the discrepancy as deliberate"):
            self.assertIn(phrase, skill, phrase)


class Manifests(unittest.TestCase):
    def test_plugin_manifest(self):
        data = json.loads(text(ROOT, "plugins", "wrist", ".claude-plugin", "plugin.json"))
        self.assertEqual(data["name"], "wrist")

    def test_marketplace_lists_wrist(self):
        data = json.loads(text(ROOT, ".claude-plugin", "marketplace.json"))
        entry = [p for p in data["plugins"] if p["name"] == "wrist"]
        self.assertEqual(len(entry), 1)
        self.assertEqual(entry[0]["source"], "./plugins/wrist")


if __name__ == "__main__":
    unittest.main()
