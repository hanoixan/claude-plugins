"""Tests for agentropy-guard's hooks. Run from the repository root:
python3 -m unittest discover -s plugins/agentropy-guard/tests"""
import json
import os
import shutil
import subprocess
import unittest

from test_guard import NOW, PLUGIN, Case, finding, g, item

HOOKS = os.path.join(PLUGIN, "hooks")
LATER = "2026-10-21T12:00:00Z"


class Hooks(Case):
    def setUp(self):
        super().setUp()
        self.cli("init")

    def event(self, **fields):
        return {"cwd": self.root, "session_id": "s1", **fields}

    def at(self, when):
        os.environ["AGENTROPY_GUARD_NOW"] = when

    def aware(self):
        return g.load_awareness(self.gstore())

    def context(self, out):
        return out["hookSpecificOutput"]["additionalContext"] if out else None


class SessionStart(Hooks):
    def test_without_a_store_it_says_nothing(self):
        shutil.rmtree(self.store)
        self.assertIsNone(g.hook_session_start(self.event()))

    def test_it_suggests_a_scan_once_a_day(self):
        text = self.context(g.hook_session_start(self.event()))
        self.assertIn("/agentropy-guard:scan", text)
        self.assertIn("no scan yet", text)
        self.assertIsNone(g.hook_session_start(self.event()))
        self.at(LATER)
        self.assertIn("/agentropy-guard:scan", self.context(g.hook_session_start(self.event())))

    def test_it_names_the_top_unknowns_as_context_only(self):
        self.cli("scanned")
        self.add_items(item())
        text = self.context(g.hook_session_start(self.event()))
        self.assertIn("ki_0001 Orders and Billing each define a Customer model", text)
        self.assertIn("do not raise it unprompted", text)

    def test_open_findings_are_listed_once_a_day(self):
        self.cli("scanned")
        self.cli("finding", "add", "--json", "-", stdin=json.dumps(finding()))
        self.assertIn("ef_0001 (medium)", self.context(g.hook_session_start(self.event())))
        self.assertIsNone(g.hook_session_start(self.event()))
        self.at(LATER)
        self.assertIn("ef_0001", self.context(g.hook_session_start(self.event())))

    def test_the_persons_own_commits_count_as_exposure(self):
        self.git_init()
        self.cli("scanned")
        self.add_items(item(), item(title="Billing owns invoices", components=["billing"],
                                    evidence=[{"type": "file", "path": "billing/invoice.py"}]))
        a = self.aware()
        a["state"]["user_edits_checked_at"] = "2020-01-01T00:00:00Z"
        g.save_awareness(self.gstore(), a)
        self.write("orders/customer.py", "x = 1\n")
        self.commit("mine")
        self.write("billing/invoice.py", "y = 1\n")
        self.commit("the agent's\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>")
        g.hook_session_start(self.event())
        items = self.aware()["items"]
        self.assertEqual([s["type"] for s in items["ki_0001"]["exposure_signals"]], ["user_edited_file"])
        self.assertNotIn("ki_0002", items)

    def test_stale_reports_why(self):
        self.assertIn("stale: no scan yet", self.cli("stale").stdout)
        self.cli("scanned")
        self.assertIn("fresh", self.cli("stale").stdout)
        self.assertIn("stale: 14 days", self.cli("stale", now="2026-11-03T12:00:00Z").stdout)


class Prompt(Hooks):
    def setUp(self):
        super().setUp()
        self.add_items(item())

    def signals(self):
        return [s["type"] for s in self.aware()["items"].get("ki_0001", {}).get("exposure_signals", [])]

    def test_naming_a_component_is_exposure(self):
        g.hook_prompt(self.event(prompt="Can billing send receipts?"))
        self.assertEqual(self.signals(), ["user_prompt_mentioned"])

    def test_two_title_words_are_exposure_and_one_is_not(self):
        g.hook_prompt(self.event(prompt="the customer flow"))
        self.assertEqual(self.signals(), [])
        g.hook_prompt(self.event(prompt="customer model cleanup"))
        self.assertEqual(self.signals(), ["user_prompt_mentioned"])

    def test_a_pending_nudge_adds_context_once(self):
        a = self.aware()
        a["state"]["pending_nudge"] = {"item": "ki_0001", "session": "s1"}
        g.save_awareness(self.gstore(), a)
        self.assertIn("answering your architecture note on ki_0001",
                      self.context(g.hook_prompt(self.event(prompt="yes please"))))
        self.assertIsNone(g.hook_prompt(self.event(prompt="next")))

    def test_another_sessions_nudge_is_ignored(self):
        a = self.aware()
        a["state"]["pending_nudge"] = {"item": "ki_0001", "session": "s0"}
        g.save_awareness(self.gstore(), a)
        self.assertIsNone(g.hook_prompt(self.event(prompt="yes")))


class PostEdit(Hooks):
    def edit(self, path, session="s1"):
        return g.hook_post_edit(self.event(session_id=session, tool_name="Edit", tool_input={"file_path": path}))

    def edits(self):
        return [e["path"] for e in g.load_pending(self.gstore())["edits"]]

    def test_an_edit_is_recorded_with_its_candidates(self):
        self.write("billing/models.py", "class Invoice:\n    pass\n")
        self.write("orders/x.py", "from billing.internal.db import conn\n")
        self.assertIsNone(self.edit(os.path.join(self.root, "orders", "x.py")))
        self.assertEqual(self.edits(), ["orders/x.py"])
        self.assertIn("boundary-drift", [c["signal"] for c in g.load_pending(self.gstore())["candidates"]])

    def test_a_relative_path_is_resolved_from_cwd(self):
        self.write("orders/x.py", "x = 1\n")
        self.edit("orders/x.py")
        self.assertEqual(self.edits(), ["orders/x.py"])

    def test_paths_outside_the_repository_and_the_store_are_ignored(self):
        self.edit("/etc/hosts")
        self.edit(os.path.join(self.root, "..", "other.py"))
        self.edit(os.path.join(self.store, "ledger.json"))
        self.assertEqual(self.edits(), [])

    def test_a_new_session_starts_a_new_edit_list(self):
        self.write("orders/a.py", "x = 1\n")
        self.write("orders/b.py", "x = 1\n")
        self.edit("orders/a.py", session="s1")
        self.edit("orders/b.py", session="s2")
        self.assertEqual(self.edits(), ["orders/b.py"])

    def test_pre_compact_and_session_end(self):
        g.hook_pre_compact(self.event())
        self.assertTrue(os.path.exists(os.path.join(self.store, g.PENDING)))
        g.hook_session_end(self.event())
        self.assertEqual(self.aware()["state"]["session_end_at"], NOW)


class Process(Hooks):
    def run_hook(self, name, stdin, path=None):
        env = {**os.environ}
        if path is not None:
            env["PATH"] = path
        return subprocess.run([shutil.which("bash"), os.path.join(HOOKS, "run.sh"), name], input=stdin,
                              capture_output=True, text=True, env=env)

    @unittest.skipUnless(shutil.which("bash"), "needs bash")
    def test_the_dispatcher_runs_a_hook(self):
        result = self.run_hook("session-start", json.dumps(self.event()))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("/agentropy-guard:scan",
                      json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"])

    @unittest.skipUnless(shutil.which("bash"), "needs bash")
    def test_broken_input_and_a_broken_ledger_are_silent(self):
        for stdin in ("not json", json.dumps(self.event())):
            self.write(".agentropy-guard/ledger.json", "{")
            result = self.run_hook("session-start", stdin)
            self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    @unittest.skipUnless(shutil.which("bash"), "needs bash")
    def test_without_python3_it_does_nothing(self):
        result = self.run_hook("session-start", json.dumps(self.event()), path=os.path.join(self.home, "empty"))
        self.assertEqual((result.returncode, result.stdout), (0, ""))

    def test_hooks_json_wires_six_events(self):
        with open(os.path.join(HOOKS, "hooks.json"), encoding="utf-8") as fh:
            hooks = json.load(fh)["hooks"]
        self.assertEqual(sorted(hooks), ["PostToolUse", "PreCompact", "SessionEnd", "SessionStart", "Stop",
                                         "UserPromptSubmit"])
        self.assertEqual(hooks["PostToolUse"][0]["matcher"], "Edit|Write|MultiEdit|NotebookEdit")
        self.assertEqual(hooks["SessionStart"][0]["matcher"], "startup|clear|compact")
        for event, name in (("SessionStart", "session-start"), ("UserPromptSubmit", "prompt"),
                            ("PostToolUse", "post-edit"), ("Stop", "stop"), ("PreCompact", "pre-compact"),
                            ("SessionEnd", "session-end")):
            self.assertEqual(hooks[event][0]["hooks"][0]["command"],
                             f'bash "${{CLAUDE_PLUGIN_ROOT}}/hooks/run.sh" {name}')
            self.assertIn(name, g.HOOKS)


class Stop(Hooks):
    def setUp(self):
        super().setUp()
        self.cli("scanned")
        self.add_items(item(evidence=[{"type": "file", "path": "orders/service.py"}],
                            importance_factors={"blast_radius": 0.9, "cross_cutting": 0.9, "irreversibility": 0.9}))
        self.transcript = os.path.join(self.home, "t.jsonl")
        self.say("Done.")

    def say(self, text):
        with open(self.transcript, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"type": "user", "message": {"role": "user", "content": "go"}}) + "\n")
            fh.write(json.dumps({"type": "assistant", "message": {"role": "assistant",
                                                                  "content": [{"type": "text", "text": text}]}}) + "\n")

    def edited(self, *paths, session="s1"):
        pend = g.load_pending(self.gstore())
        if pend["session"] != session:
            pend = {**g.empty_pending(), "session": session, "candidates": pend["candidates"]}
        pend["edits"] += [{"path": p, "at": NOW} for p in paths]
        g.save_pending(self.gstore(), pend)

    def candidate(self):
        pend = g.load_pending(self.gstore())
        found = g.candidate("boundary-drift", "medium", "x", ["orders/x.py"], ["orders", "billing"],
                            "boundary-drift|orders>billing")
        pend["candidates"].append({**found, "reviewed": False, "found_at": NOW})
        g.save_pending(self.gstore(), pend)

    def stop(self, active=False, session="s1"):
        return g.hook_stop(self.event(session_id=session, transcript_path=self.transcript, stop_hook_active=active))

    def reason(self, out):
        return out["reason"] if out else ""

    def test_an_active_stop_hook_never_blocks(self):
        self.edited("orders/service.py")
        self.candidate()
        self.assertIsNone(self.stop(active=True))

    def test_without_a_store_it_does_nothing(self):
        shutil.rmtree(self.store)
        self.assertIsNone(self.stop())

    def test_a_silent_change_is_raised(self):
        self.edited("orders/service.py")
        out = self.stop()
        self.assertEqual(out["decision"], "block")
        self.assertIn("without saying so", out["reason"])
        self.assertIn("told ki_0001 --level mentioned", out["reason"])
        self.assertEqual([s["type"] for s in self.aware()["items"]["ki_0001"]["exposure_signals"]],
                         ["agent_silent_change"])

    def test_a_change_the_reply_mentions_gets_a_nudge_instead(self):
        self.say("I updated orders/service.py.")
        self.edited("orders/service.py")
        self.assertIn("educate skill for ki_0001", self.reason(self.stop()))
        self.assertEqual(self.aware()["state"]["pending_nudge"], {"item": "ki_0001", "session": "s1"})

    def test_an_unreadable_or_garbled_transcript_skips_the_silent_check(self):
        self.transcript = os.path.join(self.home, "missing.jsonl")
        self.edited("orders/service.py")
        self.assertNotIn("without saying so", self.reason(self.stop()))
        self.transcript = os.path.join(self.home, "garbled.jsonl")
        with open(self.transcript, "w", encoding="utf-8") as fh:
            fh.write("{not json\n[1, 2]\n")
        self.at(LATER)
        self.edited("orders/service.py")
        self.assertNotIn("without saying so", self.reason(self.stop()))

    def test_one_nudge_a_day(self):
        self.say("I updated orders/service.py.")
        self.edited("orders/service.py")
        self.assertTrue(self.stop())
        self.edited("orders/service.py")
        self.assertIsNone(self.stop())
        self.at(LATER)
        self.edited("orders/service.py")
        self.assertTrue(self.stop())

    def test_two_dismissals_double_the_gap(self):
        a = self.aware()
        a["state"].update(dismissals=2, last_nudge_at=NOW)
        g.save_awareness(self.gstore(), a)
        self.say("I updated orders/service.py.")
        self.at(LATER)
        self.edited("orders/service.py")
        self.assertIsNone(self.stop())
        self.at("2026-10-22T12:00:00Z")
        self.edited("orders/service.py")
        self.assertTrue(self.stop())

    def test_an_earlier_turns_edits_are_not_counted_again(self):
        self.say("I updated orders/service.py.")
        self.edited("orders/service.py")
        self.stop()
        self.at(LATER)
        self.assertIsNone(self.stop())

    def test_candidates_go_to_the_reviewer_once(self):
        self.candidate()
        r = self.reason(self.stop())
        self.assertIn("agentropy-guard:erosion-reviewer", r)
        self.assertIn("warned --session s1", r)
        self.assertNotIn("erosion-reviewer", self.reason(self.stop()))

    def test_after_a_warning_the_session_is_not_warned_again(self):
        self.cli("warned", "--session", "s1")
        self.candidate()
        self.assertIn("Do not warn the user now", self.reason(self.stop()))


if __name__ == "__main__":
    unittest.main()
