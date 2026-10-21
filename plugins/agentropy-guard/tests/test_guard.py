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


class Items(Case):
    def ledger(self):
        return g.read_json(os.path.join(self.store, g.LEDGER), g.empty_ledger())

    def test_a_new_item_gets_an_id_times_and_importance(self):
        self.cli("init")
        self.assertIn("ki_0001 0.69 Orders and Billing", self.add_items(item()).stdout)
        it = self.ledger()["items"][0]
        self.assertEqual((it["created_at"], it["updated_at"], it["status"]), (NOW, NOW, "active"))
        self.assertEqual(it["importance_factors"]["change_frequency"], 0.0)
        self.cli("parse")

    def test_a_batch_numbers_in_order(self):
        self.cli("init")
        self.add_items(item(), item(title="Payments retry in the queue worker", origin="discovered"))
        self.assertEqual([i["id"] for i in self.ledger()["items"]], ["ki_0001", "ki_0002"])
        self.assertEqual(self.ledger()["items"][1]["importance"], 0.59)

    def test_an_invalid_item_writes_nothing(self):
        self.cli("init")
        result = self.cli("item", "add", "--json", "-", stdin=json.dumps([item(), item(category="vibes")]), ok=False)
        self.assertIn("`category` is one of", result.stderr)
        self.assertEqual(self.ledger()["items"], [])

    def test_an_update_changes_updated_at_only_when_material(self):
        self.cli("init")
        self.add_items(item())
        later = "2026-10-21T12:00:00Z"
        self.add_items({"id": "ki_0001", "importance_factors": item()["importance_factors"]}, now=later)
        self.assertEqual(self.ledger()["items"][0]["updated_at"], NOW)
        self.add_items({"id": "ki_0001", "summary": "Now three schemas."}, now=later)
        it = self.ledger()["items"][0]
        self.assertEqual((it["updated_at"], it["created_at"], it["summary"]), (later, NOW, "Now three schemas."))

    def test_an_update_of_an_unknown_id_is_refused(self):
        self.cli("init")
        result = self.cli("item", "add", "--json", "-", stdin=json.dumps({"id": "ki_0009", "summary": "x"}), ok=False)
        self.assertIn("no item ki_0009", result.stderr)

    def test_a_command_on_invalid_json_is_one_error_line(self):
        self.cli("init")
        self.write(".agentropy-guard/ledger.json", "{")
        self.assertIn("not valid JSON", self.cli("item", "list", ok=False).stderr)

    def test_change_frequency_comes_from_git(self):
        self.git_init()
        for k in range(5):
            self.write("orders/customer.py", f"x = {k}\n")
            self.commit(f"c{k}")
        self.cli("init")
        self.add_items(item())
        it = self.ledger()["items"][0]
        self.assertEqual(it["importance_factors"]["change_frequency"], 0.25)
        self.assertEqual(it["importance"], 0.74)

    def test_importance_is_capped_at_1(self):
        cfg = g.merged_config({})
        full = {**item(), "importance_factors": {k: 1.0 for k in g.FACTORS}}
        self.assertEqual(g.importance(full, cfg), 1.0)

    def test_get_list_and_supersede(self):
        self.cli("init")
        self.add_items(item(), item(title="Customer is one shared contract"))
        self.assertEqual(json.loads(self.cli("item", "get", "ki_0002").stdout)["id"], "ki_0002")
        self.cli("item", "supersede", "ki_0001", "--by", "ki_0002")
        it = self.ledger()["items"][0]
        self.assertEqual((it["status"], it["superseded_by"]), ("superseded", "ki_0002"))
        self.assertNotIn("ki_0001", self.cli("item", "list", "--status", "active").stdout)
        self.assertIn("no item ki_0009", self.cli("item", "supersede", "ki_0001", "--by", "ki_0009", ok=False).stderr)
        self.cli("parse")

    def test_refresh_recomputes_change_frequency(self):
        self.git_init()
        self.cli("init")
        self.add_items(item())
        for k in range(10):
            self.write("orders/customer.py", f"x = {k}\n")
            self.commit(f"c{k}")
        self.assertIn("1 items refreshed", self.cli("item", "refresh").stdout)
        self.assertEqual(self.ledger()["items"][0]["importance_factors"]["change_frequency"], 0.5)

    def test_scanned_records_the_scan(self):
        self.git_init()
        self.commit("first")
        self.cli("init")
        self.cli("scanned")
        last = self.ledger()["last_scan"]
        self.assertEqual(last["at"], NOW)
        self.assertRegex(last["commit"], r"^[0-9a-f]{40}$")


if __name__ == "__main__":
    unittest.main()
