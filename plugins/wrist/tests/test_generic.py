import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from support import CHECK


class FakeProfile(unittest.TestCase):
    """A two-heading profile with no story vocabulary: the checker must run it unchanged."""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="wrist-fake-")
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        prof = os.path.join(self.dir, "profiles", "poemlet")
        os.makedirs(prof)
        data = {"name": "poemlet",
                "files": [{"path": "a.md", "function": "alpha", "order": 2},
                          {"path": "b.md", "function": "beta", "order": 1}],
                "functions": {"alpha": {"heading": "alpha", "fields": ["Hue"], "children": {"bead": ["Size"]}},
                              "beta": {"heading": "beta"}},
                "relations": ["uses"], "limits": {"max_prose_words": 50}}
        with open(os.path.join(prof, "profile.json"), "w") as fh:
            json.dump(data, fh)
        self.put("wrist/PREMISE.md", "---\nprofile: poemlet\ntitle: Tiny\nslug: tiny\n---\n\n# Premise\n")
        self.put("wrist/a.md.wrist.md",
                 "# alpha: One\n\n- **Hue:** red\n- **Required:** always\n- **Rules:** none\n"
                 "- **Depends on:** [b](./b.md.wrist.md) (uses)\n- **Referred by:** none\n"
                 "- **Unknowns:** none\n\n## bead: First\n\n- **Size:** small\n")
        self.put("wrist/b.md.wrist.md",
                 "# beta: Two\n\n- **Required:** always\n- **Rules:** none\n- **Depends on:** none\n"
                 "- **Referred by:** [a](./a.md.wrist.md)\n- **Unknowns:** none\n")

    def put(self, rel, text):
        path = os.path.join(self.dir, "project", rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def run_cli(self, *args):
        env = dict(os.environ, WRIST_PROFILES_DIR=os.path.join(self.dir, "profiles"))
        proc = subprocess.run([sys.executable, CHECK, *args], cwd=os.path.join(self.dir, "project"),
                              env=env, capture_output=True, text=True)
        return proc.returncode, proc.stdout + proc.stderr

    def test_check_passes(self):
        code, out = self.run_cli("check", "wrist")
        self.assertEqual(code, 0, out)
        self.assertIn("2 stand-ins", out)

    def test_an_undeclared_heading_type_is_rejected(self):
        self.put("wrist/b.md.wrist.md", "# scene: Two\n")
        code, out = self.run_cli("check", "wrist")
        self.assertEqual(code, 1, out)
        self.assertIn("must start with `# beta: <name>`", out)

    def test_the_profile_decides_the_required_fields(self):
        with open(os.path.join(self.dir, "project", "wrist", "a.md.wrist.md"), encoding="utf-8") as fh:
            text = fh.read().replace("- **Size:** small\n", "")
        self.put("wrist/a.md.wrist.md", text)
        code, out = self.run_cli("check", "wrist")
        self.assertEqual(code, 1, out)
        self.assertIn("bead 'First' is missing `Size:`", out)


if __name__ == "__main__":
    unittest.main()
