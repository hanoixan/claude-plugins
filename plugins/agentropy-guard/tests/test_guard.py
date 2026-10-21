"""Tests for guard.py. Run from the repository root: python3 -m unittest discover -s plugins/agentropy-guard/tests"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.join(HERE, "..")
SCRIPT = os.path.join(PLUGIN, "scripts", "guard.py")
_spec = importlib.util.spec_from_file_location("guard", SCRIPT)
g = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(g)

NOW = "2026-10-20T12:00:00Z"


def item(**over):
    base = {"title": "Orders and Billing each define a Customer model", "category": "data-model",
            "summary": "Two Customer schemas, mapped by an adapter.",
            "evidence": [{"type": "file", "path": "orders/customer.py"}], "components": ["orders", "billing"],
            "importance_factors": {"blast_radius": 0.8, "cross_cutting": 0.8, "irreversibility": 0.6},
            "origin": "agent-decision"}
    base.update(over)
    return base


class Case(unittest.TestCase):
    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="agentropy-"))
        self.home = tempfile.mkdtemp(prefix="agentropy-home-")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)
        self.store = os.path.join(self.root, g.STORE)
        self.env = {"AGENTROPY_GUARD_HOME": self.home, "AGENTROPY_GUARD_NOW": NOW}
        patch = mock.patch.dict(os.environ, self.env)
        patch.start()
        self.addCleanup(patch.stop)

    def cli(self, *args, ok=True, stdin=None, now=NOW):
        env = {**os.environ, **self.env, "AGENTROPY_GUARD_NOW": now}
        result = subprocess.run([sys.executable, SCRIPT, *args, "--dir", self.store], input=stdin,
                                capture_output=True, text=True, cwd=self.root, env=env)
        if ok:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        return result

    def write(self, rel, text):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def read(self, rel):
        with open(os.path.join(self.root, rel), encoding="utf-8") as fh:
            return fh.read()

    def git_init(self):
        for cmd in (["init", "-q"], ["config", "user.name", "Ann"], ["config", "user.email", "ann@example.com"],
                    ["config", "commit.gpgsign", "false"]):
            subprocess.run(["git", "-C", self.root, *cmd], check=True)

    def commit(self, message="change", date=None):
        env = {**os.environ}
        if date:
            env.update(GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date)
        subprocess.run(["git", "-C", self.root, "add", "-A"], check=True)
        subprocess.run(["git", "-C", self.root, "commit", "-q", "--allow-empty", "-m", message], check=True, env=env)

    def gstore(self):
        return g.Store(self.store)

    def add_items(self, *items, now=NOW):
        return self.cli("item", "add", "--json", "-", stdin=json.dumps(list(items)), now=now)


class Store(Case):
    def test_init_creates_the_store_and_ignores_the_private_files(self):
        out = self.cli("init").stdout
        for name in (g.CONFIG, g.LEDGER, g.FINDINGS):
            self.assertTrue(os.path.exists(os.path.join(self.store, name)), name)
        self.assertIn("created:", out)
        ignore = self.read(".gitignore")
        self.assertIn(".agentropy-guard/pending.json\n", ignore)
        self.assertIn(".agentropy-guard/reports/\n", ignore)
        self.assertIn("already set up", self.cli("init").stdout)
        self.assertEqual(self.read(".gitignore").count("pending.json"), 1)

    def test_files_are_sorted_with_a_trailing_newline(self):
        path = os.path.join(self.root, "x.json")
        g.write_json(path, {"b": 1, "a": 2})
        with open(path, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), '{\n  "a": 2,\n  "b": 1\n}\n')

    def test_a_fresh_store_parses(self):
        self.cli("init")
        self.assertIn("0 items, 0 findings", self.cli("parse").stdout)

    def test_parse_reports_a_bad_config(self):
        self.cli("init")
        self.write(".agentropy-guard/config.json", json.dumps({"thresholds": {"importance": 2}, "colour": 1}))
        out = self.cli("parse", ok=False).stdout
        self.assertIn("unknown key `colour`", out)
        self.assertIn("`thresholds.importance` is a number from 0 to 1", out)

    def test_parse_reports_a_bad_item(self):
        self.cli("init")
        bad = {**item(category="vibes"), "id": "ki_0001", "importance": 0.5, "status": "active",
               "created_at": NOW, "updated_at": NOW}
        self.write(".agentropy-guard/ledger.json", json.dumps({"items": [bad], "last_scan": None}))
        self.assertIn("ki_0001: `category` is one of", self.cli("parse", ok=False).stdout)

    def test_invalid_json_is_one_error_line(self):
        self.cli("init")
        self.write(".agentropy-guard/ledger.json", "{")
        result = self.cli("parse", ok=False)
        self.assertIn("not valid JSON", result.stdout + result.stderr)

    def test_awareness_lives_outside_the_repository(self):
        path = self.gstore().aware_path()
        self.assertTrue(path.startswith(self.home))
        self.assertRegex(path, r"[0-9a-f]{12}[/\\]awareness\.json$")

    def test_the_store_is_at_the_git_root(self):
        self.git_init()
        sub = os.path.join(self.root, "a", "b")
        os.makedirs(sub)
        self.assertEqual(os.path.realpath(g.store_for(sub).dir), os.path.join(self.root, g.STORE))

    def test_the_merged_config_keeps_the_defaults(self):
        cfg = g.merged_config({"weights": {"agent_boost": 0.2}})
        self.assertEqual(cfg["weights"]["blast_radius"], 0.3)
        self.assertEqual(cfg["weights"]["agent_boost"], 0.2)
        self.assertEqual(cfg["rates"]["nudge_days"], 1)

    def test_no_line_is_wider_than_120_columns(self):
        for folder, _, files in os.walk(PLUGIN):
            for name in files:
                if name.endswith(".py"):
                    path = os.path.join(folder, name)
                    with open(path, encoding="utf-8") as fh:
                        for k, line in enumerate(fh, 1):
                            self.assertLessEqual(len(line.rstrip("\n")), 120, f"{path}:{k}")


if __name__ == "__main__":
    unittest.main()
