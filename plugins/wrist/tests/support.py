"""Shared fixtures for the wrist tests.

Each test copies the bundled the-lamp example into a temporary directory, breaks it in one
way, and runs the scripts as a user would.

Run from the repository root:

    python3 -m unittest discover -s plugins/wrist/tests
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.normpath(os.path.join(HERE, "..", "skills", "wrist"))
SCRIPTS = os.path.join(SKILL, "scripts")
EXAMPLE = os.path.join(SKILL, "assets", "examples", "the-lamp")
CHECK = os.path.join(SCRIPTS, "wrist_check.py")
MV = os.path.join(SCRIPTS, "wrist_mv.py")
sys.path.insert(0, SCRIPTS)

PREMISE = "wrist/PREMISE.md"
SYNOPSIS = "wrist/synopsis.md.wrist.md"
OUTLINE = "wrist/outline.md.wrist.md"
CHARACTERS = "wrist/character.md.wrist.md"
MISC = "wrist/misc.md.wrist.md"
STORY = "wrist/work/the-lamp.md.wrist.md"
NO_UNKNOWNS = "- **Unknowns:** none\n"


class TreeCase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="wrist-test-")
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        shutil.copytree(EXAMPLE, self.dir, dirs_exist_ok=True)

    def path(self, rel):
        return os.path.join(self.dir, rel)

    def read(self, rel):
        with open(self.path(rel), encoding="utf-8") as fh:
            return fh.read()

    def write(self, rel, text):
        os.makedirs(os.path.dirname(self.path(rel)), exist_ok=True)
        with open(self.path(rel), "w", encoding="utf-8") as fh:
            fh.write(text)

    def replace(self, rel, old, new):
        text = self.read(rel)
        self.assertIn(old, text, f"fixture text not found in {rel}")
        self.write(rel, text.replace(old, new, 1))

    def append(self, rel, text):
        with open(self.path(rel), "a", encoding="utf-8") as fh:
            fh.write(text)

    def run_script(self, script, *args, env=None):
        proc = subprocess.run([sys.executable, script, *args], cwd=self.dir, env=env,
                              capture_output=True, text=True)
        return proc.returncode, proc.stdout + proc.stderr

    def run_wrist(self, *args, env=None):
        return self.run_script(CHECK, *args, env=env)

    def check(self, *args):
        return self.run_wrist("check", "wrist", *args)

    def assertCheckFails(self, fragment):
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("error", out)
        self.assertIn(fragment, out)
