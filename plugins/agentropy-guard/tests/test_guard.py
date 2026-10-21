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


class Awareness(Case):
    def setUp(self):
        super().setUp()
        self.cli("init")
        self.add_items(item(), item(title="Payments retry in the queue worker", origin="discovered",
                                    evidence=[{"type": "file", "path": "worker/retry.py"}], components=["worker"]))

    def aware(self):
        return g.read_json(self.gstore().aware_path(), g.empty_awareness())

    def unknown(self, item_id, at=NOW):
        ledger = g.load_ledger(self.gstore())
        it = next(x for x in ledger["items"] if x["id"] == item_id)
        return g.unknown_likelihood(it, self.aware()["items"].get(item_id), g.merged_config({}), g.parse_time(at))

    def test_the_prior_follows_the_origin(self):
        self.assertEqual(self.unknown("ki_0001"), 0.7)
        self.assertEqual(self.unknown("ki_0002"), 0.4)

    def test_an_edit_by_the_user_lowers_it(self):
        self.cli("seen", "--path", "orders/customer.py", "--signal", "user_edited_file")
        self.assertEqual(self.unknown("ki_0001"), 0.28)
        self.assertEqual(self.unknown("ki_0002"), 0.4)

    def test_it_decays_toward_the_prior(self):
        self.cli("seen", "--item", "ki_0001", "--signal", "user_edited_file")
        self.assertEqual(self.unknown("ki_0001", "2026-11-19T12:00:00Z"), 0.49)

    def test_silent_changes_raise_it_to_a_cap(self):
        for _ in range(3):
            self.cli("seen", "--item", "ki_0001", "--signal", "agent_silent_change")
        self.assertEqual(self.unknown("ki_0001"), 0.95)

    def test_a_component_mention_lowers_it(self):
        self.cli("seen", "--component", "worker", "--signal", "user_prompt_mentioned", "--term", "worker")
        self.assertEqual(self.unknown("ki_0002"), 0.28)

    def test_seen_needs_exactly_one_target(self):
        self.assertIn("exactly one", self.cli("seen", "--signal", "user_edited_file", ok=False).stderr)

    def test_acknowledged_holds_until_the_item_changes(self):
        self.cli("respond", "ki_0001", "--response", "acknowledged")
        self.assertEqual(self.unknown("ki_0001"), 0.05)
        self.add_items({"id": "ki_0001", "summary": "Changed."}, now="2026-10-21T12:00:00Z")
        self.assertEqual(self.unknown("ki_0001"), 0.7)

    def test_told_records_the_item_version(self):
        self.cli("told", "ki_0001", "--level", "mentioned")
        rec = self.aware()["items"]["ki_0001"]
        self.assertEqual(rec["disclosures"][0]["level"], "mentioned")
        self.assertEqual(rec["item_version_at_last_disclosure"], NOW)
        self.cli("parse")

    def test_snooze_and_dismissals(self):
        self.cli("respond", "ki_0001", "--response", "snoozed")
        self.assertEqual(self.aware()["items"]["ki_0001"]["snoozed_until"], "2026-10-27T12:00:00Z")
        self.cli("respond", "ki_0001", "--response", "dismissed")
        self.cli("respond", "ki_0002", "--response", "dismissed")
        self.assertEqual(self.aware()["state"]["dismissals"], 2)
        self.cli("respond", "ki_0002", "--response", "wants_more")
        self.assertEqual(self.aware()["state"]["dismissals"], 0)


class Components(Case):
    def test_the_default_component_is_the_top_folder(self):
        cfg = g.merged_config({})
        for path, want in (("billing/x.py", "billing"), ("src/orders/a.ts", "orders"), ("./src/orders/a.ts", "orders"),
                           ("src/a.ts", None), ("README.md", None), ("docs/adr/1.md", None), (".github/ci.yml", None),
                           ("packages/web/src/app.tsx", "web")):
            self.assertEqual(g.component_of(path, cfg), want, path)

    def test_a_mapping_replaces_the_default(self):
        cfg = g.merged_config({"components": {"pay": ["services/payments/**"]}})
        self.assertEqual(g.component_of("services/payments/a.py", cfg), "pay")
        self.assertIsNone(g.component_of("billing/x.py", cfg))


class Queue(Case):
    def setUp(self):
        super().setUp()
        self.cli("init")
        self.add_items(item(),
                       item(title="Payments retry in the queue worker", origin="discovered"),
                       item(title="Billing owns invoices", origin="human-decision"),
                       item(title="Search index rebuilds nightly", components=["search"],
                            evidence=[{"type": "file", "path": "search/index.py"}],
                            importance_factors={"blast_radius": 0.5, "cross_cutting": 0.5, "irreversibility": 0.5}))

    def ids(self, *args, now=NOW):
        return [r["id"] for r in json.loads(self.cli("queue", "--json", *args, now=now).stdout)]

    def test_only_important_probably_unknown_items_are_queued(self):
        rows = json.loads(self.cli("queue", "--json").stdout)
        self.assertEqual([(r["id"], r["priority"]) for r in rows], [("ki_0001", 0.483), ("ki_0004", 0.35)])

    def test_relevance_reorders(self):
        self.assertEqual(self.ids("--files", "search/index.py"), ["ki_0004", "ki_0001"])
        self.assertEqual(self.ids("--files", "search/other.py"), ["ki_0004", "ki_0001"])
        self.assertEqual(self.ids("--components", "billing"), ["ki_0001", "ki_0004"])

    def test_a_disclosed_item_waits_until_it_changes(self):
        self.cli("told", "ki_0001", "--level", "mentioned")
        self.assertEqual(self.ids(), ["ki_0004"])
        later = "2026-10-21T12:00:00Z"
        self.add_items({"id": "ki_0001", "summary": "Now three schemas."}, now=later)
        self.assertEqual(self.ids(now=later), ["ki_0001", "ki_0004"])

    def test_a_snoozed_item_returns_after_the_snooze(self):
        self.cli("respond", "ki_0001", "--response", "snoozed")
        self.assertEqual(self.ids(), ["ki_0004"])
        self.assertEqual(self.ids(now="2026-10-28T12:00:00Z"), ["ki_0001", "ki_0004"])

    def test_superseded_items_are_left_out(self):
        self.cli("item", "supersede", "ki_0001", "--by", "ki_0004")
        self.assertEqual(self.ids(), ["ki_0004"])

    def test_the_text_view_explains_the_score(self):
        out = self.cli("queue", "--limit", "1").stdout
        self.assertIn("ki_0001 priority 0.48 (importance 0.69 x unknown 0.70 x relevance 1)", out)
        self.assertNotIn("ki_0004", out)


class Graph(Case):
    def setUp(self):
        super().setUp()
        self.write("orders/service.py", "from billing.models import Customer\nimport json\n")
        self.write("billing/models.py", "class Customer:\n    pass\n")
        self.write("web/src/app.ts", 'import { x } from "../../orders/api";\nconst y = require(\'billing/client\');\n')
        self.write("svc/main.go", 'package main\n\nimport (\n\t"fmt"\n\t"example.com/app/billing/pay"\n)\n')
        self.write("billing/client.ts", "export const client = 1;\n")
        self.write("billing/pay/pay.go", "package pay\n")
        self.write("orders/api.ts", "export const api = 1;\n")
        self.write("core/lib.rs", "use crate::orders::Order;\n")
        self.write("docs/readme.md", "billing\n")
        self.cli("init")

    def test_imports_by_language(self):
        self.assertEqual(g.imports_of("a.py", "import a.b\nfrom ..c import d\nfrom . import e\n"), ["a.b", "..c", "."])
        self.assertEqual(g.imports_of("a.ts", 'export { a } from "./x";\nimport "./side";\nawait import("./lazy");\n'),
                         ["./x", "./side", "./lazy"])
        self.assertEqual(g.imports_of("A.java", "import static com.acme.billing.Pay.run;\n"),
                         ["com.acme.billing.Pay.run"])
        self.assertEqual(g.imports_of("a.cs", "using Acme.Billing;\n"), ["Acme.Billing"])
        self.assertEqual(g.imports_of("a.c", '#include "billing/pay.h"\n#include <stdio.h>\n'), ["billing/pay.h"])
        self.assertEqual(g.imports_of("a.md", "import x"), [])

    def test_a_relative_python_import_stays_in_its_component(self):
        cfg = g.merged_config({})
        self.assertEqual(g.import_target("..billing.x", "orders/sub/a.py", cfg, {"orders", "billing"}), "orders")
        self.assertEqual(g.import_target("billing.models", "orders/a.py", cfg, {"orders", "billing"}), "billing")

    def test_the_graph_has_the_cross_component_edges(self):
        data = json.loads(self.cli("graph", "--json").stdout)
        self.assertEqual(data["components"], ["billing", "core", "orders", "svc", "web"])
        self.assertEqual([(e["from"], e["to"], e["count"]) for e in data["edges"]],
                         [("core", "orders", 1), ("orders", "billing", 1), ("svc", "billing", 1), ("web", "billing", 1),
                          ("web", "orders", 1)])
        self.assertIn("orders -> billing (1)", self.cli("graph").stdout)

    def test_large_and_binary_files_are_not_read(self):
        self.write("orders/big.py", "x = 1\n" * 50000)
        with open(os.path.join(self.root, "orders", "blob.py"), "wb") as fh:
            fh.write(b"import billing\0\0")
        self.assertIsNone(g.read_source(self.gstore(), "orders/big.py"))
        self.assertIsNone(g.read_source(self.gstore(), "orders/blob.py"))
        self.assertIsNone(g.read_source(self.gstore(), "orders/missing.py"))


def finding(**over):
    base = {"signal": "adapter-proliferation", "severity": "medium",
            "description": "Two adapters between orders and billing.",
            "evidence": [{"type": "file", "path": "orders/customer_adapter.py"}], "components": ["billing", "orders"],
            "conway_mechanism": 2, "suggested_countermove": "Define a shared Customer contract.", "cost": "1-2 hours"}
    base.update(over)
    return base


class Erosion(Case):
    def setUp(self):
        super().setUp()
        self.write("billing/models.py", "class Invoice:\n    pass\n")
        self.write("billing/api.py", "def charge():\n    pass\n")
        self.write("billing/internal/db.py", "conn = 1\n")
        self.write("orders/models.py", "class Order:\n    pass\n")
        self.cli("init")

    def detect(self, path):
        return g.detect_file(self.gstore(), g.config(self.gstore()), path)

    def signals(self, path):
        return [(c["signal"], c["severity"]) for c in self.detect(path)]

    def test_adapters_between_the_same_pair_escalate(self):
        self.write("orders/customer_adapter.py", "from billing.models import Invoice\n")
        self.assertIn(("adapter-proliferation", "low"), self.signals("orders/customer_adapter.py"))
        self.write("billing/sync_orders.py", "from orders.models import Order\n")
        self.assertIn(("adapter-proliferation", "medium"), self.signals("orders/customer_adapter.py"))
        self.write("orders/billing_mapper.py", "import billing.api\n")
        self.assertIn(("adapter-proliferation", "high"), self.signals("orders/customer_adapter.py"))

    def test_an_ordinary_cross_import_is_not_an_adapter(self):
        self.write("orders/service.py", "from billing.models import Invoice\n")
        self.assertNotIn("adapter-proliferation", [s for s, _ in self.signals("orders/service.py")])

    def test_a_model_defined_twice_is_found(self):
        self.write("orders/models.py", "class Customer:\n    pass\nclass Config:\n    pass\n")
        self.write("billing/types.ts", "export interface BillingCustomer {\n  id: string\n}\nexport class Config {}\n")
        dup = [c for c in self.detect("orders/models.py") if c["signal"] == "duplicate-model"]
        self.assertEqual([(c["description"], c["components"]) for c in dup],
                         [("Customer is defined separately in billing, orders", ["billing", "orders"])])

    def test_a_new_import_into_another_component(self):
        self.git_init()
        self.write("orders/service.py", "import json\n")
        self.commit()
        self.write("orders/service.py", "import json\nfrom billing import api\n")
        self.assertIn(("point-to-point", "low"), self.signals("orders/service.py"))
        self.commit()
        self.assertNotIn("point-to-point", [s for s, _ in self.signals("orders/service.py")])

    def test_an_allowed_edge_is_not_flagged(self):
        self.write(".agentropy-guard/config.json", json.dumps({"allowed_edges": [["orders", "billing"]]}))
        self.write("orders/service.py", "from billing import api\n")
        self.assertNotIn("point-to-point", [s for s, _ in self.signals("orders/service.py")])

    def test_reaching_into_internals(self):
        self.write("orders/x.py", "from billing.internal.db import conn\n")
        self.assertIn(("boundary-drift", "medium"), self.signals("orders/x.py"))

    def test_a_change_across_components_without_a_contract(self):
        self.write("orders/service.py", "from billing import api\n")
        store, cfg = self.gstore(), g.config(self.gstore())
        ledger = g.load_ledger(store)
        found = g.turn_candidates(store, cfg, ["orders/service.py", "billing/api.py"], ledger)
        self.assertEqual([(c["signal"], c["severity"]) for c in found], [("private-contract", "medium")])
        self.write("contracts/customer.json", "{}")
        self.assertEqual(g.turn_candidates(store, cfg, ["orders/service.py", "billing/api.py",
                                                        "contracts/customer.json"], ledger), [])

    def test_an_important_change_without_a_decision_record(self):
        self.add_items(item(evidence=[{"type": "file", "path": "orders/service.py"}],
                            importance_factors={"blast_radius": 0.9, "cross_cutting": 0.9, "irreversibility": 0.9}))
        store, cfg = self.gstore(), g.config(self.gstore())
        ledger = g.load_ledger(store)
        found = g.turn_candidates(store, cfg, ["orders/service.py"], ledger)
        self.assertEqual([(c["signal"], c["key"]) for c in found],
                         [("missing-decision-record", "missing-decision-record|ki_0001")])
        self.assertEqual(g.turn_candidates(store, cfg, ["orders/service.py", "docs/adr/0001-customer.md"], ledger), [])

    def test_contract_churn_from_history(self):
        self.git_init()
        for k in range(5):
            self.write("contracts/customer.json", json.dumps({"v": k}))
            self.commit(f"c{k}")
        found = g.history_candidates(self.gstore(), g.config(self.gstore()))
        self.assertEqual([(c["signal"], c["severity"]) for c in found], [("contract-churn", "medium")])

    def test_huge_and_binary_files_are_skipped(self):
        self.write("orders/big_adapter.py", "from billing import api\n" + "x = 1\n" * 50000)
        self.assertEqual(self.detect("orders/big_adapter.py"), [])

    def test_a_disabled_detector_does_not_run(self):
        self.write(".agentropy-guard/config.json", json.dumps({"detectors": {"boundary-drift": False}}))
        self.write("orders/x.py", "from billing.internal.db import conn\n")
        self.assertNotIn("boundary-drift", [s for s, _ in self.signals("orders/x.py")])

    def test_findings_merge_and_respect_decisions(self):
        add = lambda f: self.cli("finding", "add", "--json", "-", stdin=json.dumps(f)).stdout
        self.assertIn("ef_0001 new", add(finding()))
        self.assertIn("ef_0001 updated", add(finding(evidence=[{"type": "file", "path": "billing/sync_orders.py"}])))
        data = g.load_findings(self.gstore())["findings"]
        self.assertEqual(len(data[0]["evidence"]), 2)
        self.cli("finding", "decide", "ef_0001", "--decision", "false-positive")
        self.assertIn("ef_0001 already decided", add(finding()))
        self.assertIn("ef_0002 new", add(finding(severity="high")))
        self.assertIn("ef_0002", self.cli("finding", "list", "--status", "open").stdout)
        self.assertNotIn("ef_0002", self.cli("finding", "list", "--status", "decided").stdout)
        self.cli("parse")

    def test_an_invalid_finding_writes_nothing(self):
        result = self.cli("finding", "add", "--json", "-", stdin=json.dumps(finding(conway_mechanism=9)), ok=False)
        self.assertIn("`conway_mechanism`", result.stderr)
        self.assertEqual(g.load_findings(self.gstore())["findings"], [])

    def test_candidates_skip_known_findings_and_can_be_cleared(self):
        self.cli("finding", "add", "--json", "-", stdin=json.dumps(finding()))
        pend, findings = g.load_pending(self.gstore()), g.load_findings(self.gstore())
        same = g.candidate("adapter-proliferation", "medium", "x", ["orders/a_adapter.py"], ["billing", "orders"],
                           "adapter-proliferation|billing,orders")
        other = g.candidate("boundary-drift", "medium", "y", ["orders/x.py"], ["orders", "billing"],
                            "boundary-drift|orders>billing")
        self.assertEqual(g.add_candidates(pend, [same, other], findings, g.now()), 1)
        g.save_pending(self.gstore(), pend)
        self.assertEqual([c["key"] for c in json.loads(self.cli("candidates").stdout)],
                         ["boundary-drift|orders>billing"])
        self.cli("candidates", "--clear")
        self.assertEqual(json.loads(self.cli("candidates").stdout), [])

    def test_signals_prints_candidates(self):
        self.write("orders/x.py", "from billing.internal.db import conn\n")
        data = json.loads(self.cli("signals", "--paths", "orders/x.py").stdout)
        self.assertIn("boundary-drift", [c["signal"] for c in data])

    def test_warned_marks_the_session(self):
        self.cli("warned", "--session", "s1")
        self.assertEqual(g.load_awareness(self.gstore())["state"]["high_shown_session"], "s1")


if __name__ == "__main__":
    unittest.main()
