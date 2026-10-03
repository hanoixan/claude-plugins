"""Tests for wrist_check.py and wrist_mv.py.

Each test copies the bundled undo-system example into a temporary directory,
breaks it in one way, and runs the script as a user would.

Run from the repository root:

    python3 -m unittest discover -s plugins/wrist/tests
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

SKILL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "skills", "wrist")
EXAMPLE = os.path.join(SKILL, "assets", "examples", "undo-system", "wrist")
CHECK = os.path.join(SKILL, "scripts", "wrist_check.py")
MV = os.path.join(SKILL, "scripts", "wrist_mv.py")

COMMAND = "wrist/undo/command.code.wrist.md"
TRANSACTION = "wrist/undo/transaction.code.wrist.md"
HISTORY = "wrist/undo/history.code.wrist.md"
STORE = "wrist/infra/history_store.iac.wrist.md"
SYSTEM = "wrist/SYSTEM.md"
SNAPSHOT = "wrist/undo/history_snapshot.data.wrist.md"
NO_UNKNOWNS = "- **Unknowns:** none\n"
FRONT = "---\nrole: product\n---\n"

BACKLINK = "- **Referred by:** [Transaction](./transaction.code.wrist.md#class-transaction)\n"
COMMAND_LINK = "./command.code.wrist.md#class-command"


class TreeCase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="wrist-test-")
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        shutil.copytree(EXAMPLE, os.path.join(self.dir, "wrist"))

    def path(self, rel):
        return os.path.join(self.dir, rel)

    def replace(self, rel, old, new):
        with open(self.path(rel), encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn(old, text, f"fixture text not found in {rel}")
        with open(self.path(rel), "w", encoding="utf-8") as fh:
            fh.write(text.replace(old, new, 1))

    def append(self, rel, text):
        with open(self.path(rel), "a", encoding="utf-8") as fh:
            fh.write(text)

    def front(self, rel, *lines):
        """Replace a stand-in's `role: product` front matter with these lines; no lines removes it."""
        self.replace(rel, FRONT, "---\n" + "\n".join(lines) + "\n---\n" if lines else "")

    def run_script(self, script, *args):
        proc = subprocess.run([sys.executable, script, *args], cwd=self.dir,
                              capture_output=True, text=True)
        return proc.returncode, proc.stdout + proc.stderr

    def check(self, *args):
        return self.run_script(CHECK, "check", "wrist", *args)

    def assertCheckFails(self, fragment):
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("error", out)
        self.assertIn(fragment, out)


class MiniTree(unittest.TestCase):
    """A tree built from scratch. The stand-ins are stubs: only their paths, front matter and links matter."""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="wrist-mini-")
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        os.makedirs(os.path.join(self.dir, "wrist"))

    def file(self, rel):
        return os.path.join(self.dir, "wrist", rel + ".wrist.md")

    def stand_in(self, rel, depends=(), front=None, body=()):
        path = self.file(rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        lines = ["---", *front, "---"] if front else []
        lines += [f"# module: {os.path.basename(rel)}", "", *body]
        for dep in depends:
            lines.append(f"- **Depends on:** [{dep}]({os.path.relpath(self.file(dep), os.path.dirname(path))})")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")

    def read(self, rel):
        with open(self.file(rel), encoding="utf-8") as fh:
            return fh.read()

    def run_check(self, *args):
        proc = subprocess.run([sys.executable, CHECK, *args], cwd=self.dir, capture_output=True, text=True)
        return proc.returncode, proc.stdout + proc.stderr

    def untested(self):
        """Relative paths that `untested_units` reports, called directly: the stubs would not pass `check`."""
        sys.path.insert(0, os.path.dirname(CHECK))
        self.addCleanup(sys.path.remove, os.path.dirname(CHECK))
        import wrist_check
        wrist_root, files = wrist_check.load_tree(os.path.join(self.dir, "wrist"))
        deps, _ = wrist_check.build_edges(wrist_root, files, report=False)
        primary = wrist_check.resolve_units(files, report=False)
        return sorted(sf.rel for sf in wrist_check.untested_units(files, deps, primary))


class CheckAcceptsTheExample(TreeCase):
    def test_pristine_example_has_no_errors_or_warnings(self):
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("0 errors, 0 warnings", out)

    def test_left_over_arguments_are_rejected(self):
        code, out = self.run_script(CHECK, "check", "wrist", "extra")
        self.assertEqual(code, 2, out)
        self.assertIn("unrecognized arguments: extra", out)


class CheckRejectsBrokenTrees(TreeCase):
    def test_deleted_backlink(self):
        self.replace(COMMAND, BACKLINK, "")
        self.assertCheckFails("missing backlink")

    def test_function_missing_returns(self):
        self.replace(TRANSACTION, "- **Returns:** success or failure.\n", "")
        self.assertCheckFails("is missing `Returns:`")

    def test_module_missing_owns(self):
        self.replace(TRANSACTION, "- **Owns:** the `Transaction` composite.\n", "")
        self.assertCheckFails("is missing `Owns:`")

    def test_missing_required(self):
        self.replace(TRANSACTION, "- **Required:** always.\n", "")
        self.assertCheckFails("missing `Required:`")

    def test_no_unknowns_declaration(self):
        self.replace(TRANSACTION, "- **Unknowns:** none\n", "")
        self.assertCheckFails("no *UNKNOWN* entries")

    def test_link_to_missing_file(self):
        self.replace(TRANSACTION, COMMAND_LINK, "./nope.code.wrist.md#class-command")
        self.assertCheckFails("link target does not exist")

    def test_untagged_fence(self):
        self.replace(COMMAND, "```text", "```")
        self.assertCheckFails("code fence has no language tag")

    def test_wrong_top_heading(self):
        self.replace(TRANSACTION, "# module: transaction", "# class: transaction")
        self.assertCheckFails("must start with `# module: <name>`")

    def test_resource_missing_data_requirements(self):
        self.replace(STORE, "- **Data requirements:**", "- **Notes:**")
        self.assertCheckFails("is missing `Data requirements:`")

    def test_name_without_extension(self):
        os.rename(self.path(TRANSACTION), self.path("wrist/undo/transaction.wrist.md"))
        self.assertCheckFails("stand-in name must be")

    def test_link_fragment_matching_no_heading_in_another_file(self):
        self.replace(TRANSACTION, COMMAND_LINK, "./command.code.wrist.md#class-nosuch")
        self.assertCheckFails("fragment '#class-nosuch' does not match any heading")

    def test_link_fragment_matching_no_heading_in_the_same_file(self):
        self.replace(TRANSACTION, "- **Unknowns:** none\n",
                     "- **Unknowns:** none\n- **Depends on:** [Transaction.nosuch](#function-nosuch)\n")
        self.assertCheckFails("fragment '#function-nosuch' does not match any heading")


class CheckWarnings(TreeCase):
    def test_unknown_without_consequence_warns_and_passes(self):
        self.replace(STORE, " Consequence: placeholder `.iac`; retention and access cannot be implemented."
                            " Unlocks: renaming to a real IaC format (e.g. `.tf`) or a local-storage config module.", "")
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("should state `Consequence:` and `Unlocks:`", out)

    def test_dotted_link_text_naming_the_wrong_owner_warns(self):
        self.replace(TRANSACTION, "[UndoHistory.begin_group](./history.code.wrist.md#function-begin_group)",
                     "[Transaction.begin_group](./history.code.wrist.md#function-begin_group)")
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("warning", out)
        self.assertIn("link text 'Transaction.begin_group'", out)
        self.assertIn("UndoHistory.begin_group", out)

    def test_dotted_link_text_to_a_free_function_warns(self):
        # A method demoted to a free function keeps its slug, so only the name can catch it.
        self.replace(HISTORY, "### function: serialize", "## function: serialize")
        code, out = self.check()
        self.assertIn("link text 'UndoHistory.serialize'", out)


class LenientMode(TreeCase):
    def test_missing_field_is_only_a_warning(self):
        self.replace(TRANSACTION, "- **Returns:** success or failure.\n", "")
        code, out = self.check("--lenient")
        self.assertEqual(code, 0, out)
        self.assertIn("warning: function 'apply' is missing `Returns:`", out)

    def test_missing_backlink_is_still_an_error(self):
        self.replace(COMMAND, BACKLINK, "")
        code, out = self.check("--lenient")
        self.assertEqual(code, 1, out)
        self.assertIn("missing backlink", out)


class SystemFile(TreeCase):
    def test_check_and_unknowns_report_the_same_count(self):
        _, checked = self.check()
        _, listed = self.run_script(CHECK, "unknowns", "wrist")
        self.assertIn("9 unknowns", listed)
        self.assertIn("9 unknowns", checked)

    def test_link_to_missing_file_in_system_file(self):
        self.append(SYSTEM, "\nSee [gone](./undo/gone.code.wrist.md).\n")
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("SYSTEM.md", out)
        self.assertIn("link target does not exist", out)

    def test_dangling_fragment_in_system_file(self):
        self.append(SYSTEM, "\nSee [UndoHistory.nosuch](./undo/history.code.wrist.md#function-nosuch).\n")
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("SYSTEM.md", out)
        self.assertIn("fragment '#function-nosuch' does not match any heading", out)

    def test_links_inside_fences_in_system_file_are_ignored(self):
        self.append(SYSTEM, "\n```text\n[gone](./undo/gone.code.wrist.md)\n```\n")
        code, out = self.check()
        self.assertEqual(code, 0, out)


class UnknownsCommand(TreeCase):
    """TRANSACTION and COMMAND both say `Unknowns: none`; tests swap that line for a marker."""

    def unknowns(self, *args):
        return self.run_script(CHECK, "unknowns", "wrist", *args)

    def declare(self, rel, text, marker="*UNKNOWN*"):
        self.replace(rel, NO_UNKNOWNS, f"{marker}: {text}\n")

    def group(self, out, title):
        lines = out.splitlines()
        start = next((i for i, l in enumerate(lines) if l.startswith(title + " (")), None)
        self.assertIsNotNone(start, f"no '{title}' group in:\n{out}")
        body = []
        for line in lines[start + 1:]:
            if not line.strip():
                break
            body.append(line)
        return body

    def count(self, out):
        return int(re.search(r"(\d+) unknowns", out).group(1))

    def test_local_unknown_is_listed_under_local(self):
        self.declare(TRANSACTION, "[retry] How many retries. Kind: local. Proposed: three. Consequence: c. Unlocks: u.")
        _, out = self.unknowns()
        body = self.group(out, "Local")
        self.assertTrue(any(l.startswith("- [retry] undo/transaction.code.wrist.md:") and
                            l.endswith("(module: transaction): How many retries. Kind: local. "
                                       "Proposed: three. Consequence: c. Unlocks: u.") for l in body), body)

    def test_blocking_unknown_is_listed_under_blocking(self):
        self.declare(COMMAND, "Which wire format. Kind: blocking. Consequence: c. Unlocks: u.")
        _, out = self.unknowns()
        body = self.group(out, "Blocking")
        self.assertTrue(any("undo/command.code.wrist.md:" in l and "Which wire format." in l for l in body), body)

    def test_unknown_without_kind_is_listed_under_no_valid_kind(self):
        self.declare(COMMAND, "Something open. Consequence: c. Unlocks: u.")
        _, out = self.unknowns()
        body = self.group(out, "No valid kind")
        self.assertTrue(any("Something open." in l for l in body), body)

    def test_invalid_kind_is_listed_under_no_valid_kind(self):
        self.declare(COMMAND, "Something open. Kind: maybe. Consequence: c. Unlocks: u.")
        _, out = self.unknowns()
        body = self.group(out, "No valid kind")
        self.assertTrue(any("Something open." in l for l in body), body)

    def test_json_items_share_one_shape(self):
        self.declare(COMMAND, "Follows [nosuch]. Consequence: unspecified here.")
        _, out = self.unknowns("--json")
        items = json.loads(out)
        keys = {"file", "line", "where", "text", "name", "follows", "kind", "proposed", "consequence",
                "unlocks", "followers"}
        for item in items:
            self.assertEqual(set(item), keys, item)
        self.assertEqual([i["follows"] for i in items if i["follows"]], ["nosuch"])

    def test_bold_marker_with_the_colon_inside_is_an_unknown(self):
        self.replace(TRANSACTION, NO_UNKNOWNS,
                     "**UNKNOWN:** [retry] How many retries. Kind: local. Proposed: three. Consequence: c. Unlocks: u.\n")
        _, out = self.unknowns("--json")
        self.assertEqual([i["kind"] for i in json.loads(out) if i["name"] == "retry"], ["local"])

    def test_clauses_may_come_in_any_order(self):
        self.declare(TRANSACTION, "[retry] How many retries. Unlocks: u. Consequence: c. Proposed: three. Kind: local.")
        _, out = self.unknowns("--json")
        item = next(i for i in json.loads(out) if i["name"] == "retry")
        self.assertEqual((item["kind"], item["proposed"], item["consequence"], item["unlocks"]),
                         ("local", "three.", "c.", "u."))

    def test_follower_is_listed_under_its_decision(self):
        self.declare(TRANSACTION, "[retry] How many retries. Kind: local. Proposed: three. Consequence: c. Unlocks: u.")
        self.declare(COMMAND, "Follows [retry]. Consequence: the retry loop here is unspecified.")
        _, out = self.unknowns()
        body = self.group(out, "Local")
        index = next(i for i, l in enumerate(body) if l.startswith("- [retry] "))
        follower = body[index + 1]
        self.assertTrue(follower.startswith("    followed at undo/command.code.wrist.md:"), follower)
        self.assertTrue(follower.endswith("(module: command): the retry loop here is unspecified."), follower)

    def test_followers_are_not_counted(self):
        before = self.count(self.unknowns()[1])
        self.declare(TRANSACTION, "[retry] How many retries. Kind: local. Proposed: three. Consequence: c. Unlocks: u.")
        self.declare(COMMAND, "Follows [retry]. Consequence: unspecified here.")
        self.assertEqual(self.count(self.unknowns()[1]), before + 1)

    def test_follower_of_an_undeclared_name_is_listed_apart(self):
        self.declare(COMMAND, "Follows [nosuch]. Consequence: unspecified here.")
        _, out = self.unknowns()
        body = self.group(out, "Following an undeclared name")
        self.assertTrue(any("undo/command.code.wrist.md:" in l and "Follows [nosuch]" in l for l in body), body)

    def test_unknown_starting_with_a_link_is_not_named_after_it(self):
        self.declare(TRANSACTION, "[command](./command.code.wrist.md) may gain a method. "
                                  "Kind: blocking. Consequence: c. Unlocks: u.")
        _, out = self.unknowns("--json")
        item = next(i for i in json.loads(out) if "may gain a method" in i["text"])
        self.assertIsNone(item["name"])

    def test_double_star_marker_parses_the_same(self):
        text = "[retry] How many retries. Kind: local. Proposed: three. Consequence: c. Unlocks: u."

        def parsed(marker):
            tree = tempfile.mkdtemp(prefix="wrist-test-")
            self.addCleanup(shutil.rmtree, tree, ignore_errors=True)
            shutil.copytree(EXAMPLE, os.path.join(tree, "wrist"))
            path = os.path.join(tree, TRANSACTION)
            with open(path, encoding="utf-8") as fh:
                body = fh.read()
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(body.replace(NO_UNKNOWNS, f"{marker}: {text}\n"))
            proc = subprocess.run([sys.executable, CHECK, "unknowns", "wrist", "--json"], cwd=tree,
                                  capture_output=True, text=True)
            return next(i for i in json.loads(proc.stdout) if i["name"] == "retry")

        self.assertEqual(parsed("*UNKNOWN*"), parsed("**UNKNOWN**"))

    def test_json_carries_the_parsed_fields(self):
        self.declare(TRANSACTION, "[retry] How many retries. Kind: local. Proposed: three. Consequence: c. Unlocks: u.")
        self.declare(COMMAND, "Follows [retry]. Consequence: unspecified here.")
        _, out = self.unknowns("--json")
        item = next(i for i in json.loads(out) if i.get("name") == "retry")
        self.assertEqual(item["file"], "undo/transaction.code.wrist.md")
        self.assertEqual(item["where"], "module: transaction")
        self.assertEqual(item["kind"], "local")
        self.assertEqual(item["proposed"], "three.")
        self.assertEqual(item["consequence"], "c.")
        self.assertEqual(item["unlocks"], "u.")
        self.assertEqual(len(item["followers"]), 1)
        follower = item["followers"][0]
        self.assertEqual(follower["file"], "undo/command.code.wrist.md")
        self.assertEqual(follower["where"], "module: command")
        self.assertEqual(follower["consequence"], "unspecified here.")
        self.assertIsInstance(follower["line"], int)

    def test_label_word_inside_a_clause_value_does_not_start_a_clause(self):
        self.declare(TRANSACTION, "[workload] Which workload. Kind: local. Proposed: a Deployment; the consequence: "
                                  "no stable identity. Consequence: manifests say so. Unlocks: u.")
        _, out = self.unknowns("--json")
        item = next(i for i in json.loads(out) if i.get("name") == "workload")
        self.assertEqual(item["proposed"], "a Deployment; the consequence: no stable identity.")
        self.assertEqual(item["consequence"], "manifests say so.")

    def test_label_word_inside_a_follower_consequence_is_kept(self):
        self.declare(TRANSACTION, "[retry] How many retries. Kind: local. Proposed: three. Consequence: c. Unlocks: u.")
        self.declare(COMMAND, "Follows [retry]. Consequence: the manifest keeps `kind: Deployment` here.")
        _, out = self.unknowns()
        self.assertIn("(module: command): the manifest keeps `kind: Deployment` here.", out)

    def test_bold_clause_labels_are_read(self):
        self.declare(TRANSACTION, "[retry] How many retries. **Kind:** local. **Proposed:** three. "
                                  "**Consequence:** c. **Unlocks:** u.")
        _, out = self.unknowns("--json")
        item = next(i for i in json.loads(out) if i.get("name") == "retry")
        self.assertEqual((item["kind"], item["proposed"], item["unlocks"]), ("local", "three.", "u."))

    def test_heading_with_brackets_is_printed_whole(self):
        self.replace(TRANSACTION, "# module: transaction", "# module: transaction (grouping)")
        self.declare(TRANSACTION, "[retry] How many retries. Kind: local. Proposed: three. Consequence: c. Unlocks: u.")
        _, out = self.unknowns()
        self.assertIn("(module: transaction (grouping)): How many retries.", out)

    def test_json_keeps_the_original_keys_on_every_item(self):
        _, out = self.unknowns("--json")
        for item in json.loads(out):
            for key in ("file", "line", "where", "text"):
                self.assertIn(key, item)

    def test_tree_with_no_unknowns_says_so(self):
        os.makedirs(self.path("empty"))
        code, out = self.run_script(CHECK, "unknowns", "empty")
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "No unknowns.")


class UnknownRules(TreeCase):
    KIND = " Kind: blocking."

    def test_example_groups_its_decisions(self):
        _, out = self.run_script(CHECK, "unknowns", "wrist")
        self.assertIn("Blocking (8):", out)
        self.assertIn("Local (1):", out)
        self.assertIn("    followed at infra/history_store.iac.wrist.md:", out)
        self.assertIn("9 unknowns", out)

    def test_example_marks_a_function_that_follows_a_decision(self):
        _, out = self.run_script(CHECK, "unknowns", "wrist")
        self.assertIn("    followed at undo/history.code.wrist.md:", out)
        self.assertIn("function: serialize): this function is deleted if cross-session undo is not required.", out)
        self.assertIn("9 unknowns", out)

    def test_system_file_decision_is_labelled_without_doubled_brackets(self):
        _, out = self.run_script(CHECK, "unknowns", "wrist")
        self.assertIn("- [language] SYSTEM.md:21 (system): Implementation language and runtime.", out)

    def test_declaration_without_kind_is_an_error(self):
        self.replace(STORE, self.KIND, "")
        self.assertCheckFails("*UNKNOWN* is missing `Kind:` (blocking or local)")

    def test_declaration_without_kind_is_a_warning_when_lenient(self):
        self.replace(STORE, self.KIND, "")
        code, out = self.check("--lenient")
        self.assertEqual(code, 0, out)
        self.assertIn("warning: *UNKNOWN* is missing `Kind:`", out)

    def test_kind_must_be_blocking_or_local(self):
        self.replace(STORE, self.KIND, " Kind: maybe.")
        self.assertCheckFails("*UNKNOWN* has `Kind: maybe`; it must be blocking or local")

    def test_local_unknown_needs_a_proposal(self):
        self.replace(HISTORY, " Proposed: 1000 steps.", "")
        self.assertCheckFails("*UNKNOWN* with `Kind: local` needs `Proposed:`")

    def test_follower_of_an_undeclared_name_is_an_error(self):
        self.replace(STORE, "Follows [cross-session-undo]", "Follows [nosuch]")
        self.assertCheckFails("`Follows [nosuch]` matches no declared unknown")

    def test_duplicate_name_is_an_error(self):
        self.replace(SYSTEM, "[language]", "[cross-session-undo]")
        self.assertCheckFails("unknown name [cross-session-undo] is already declared at")

    def test_system_file_unknown_without_kind_is_an_error(self):
        self.replace(SYSTEM, "[language] Implementation language and runtime. Kind: blocking.",
                     "[language] Implementation language and runtime.")
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("SYSTEM.md", out)
        self.assertIn("*UNKNOWN* is missing `Kind:`", out)

    def test_follower_stands_in_for_unknowns_none(self):
        self.replace(TRANSACTION, NO_UNKNOWNS,
                     "*UNKNOWN*: Follows [cross-session-undo]. Consequence: grouping is unaffected.\n")
        code, out = self.check()
        self.assertEqual(code, 0, out)

    def test_follower_without_consequence_warns(self):
        self.replace(STORE, " Consequence: this resource is deleted if cross-session undo is not required.", "")
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("warning: *UNKNOWN* that follows another should state `Consequence:`", out)

    def test_unknown_as_a_field_value_is_validated(self):
        self.replace(TRANSACTION, "- **Returns:** success or failure.\n",
                     "- **Returns:** *UNKNOWN*: whether partial success is reported. Consequence: c. Unlocks: u.\n")
        self.assertCheckFails("*UNKNOWN* is missing `Kind:`")

    def test_fenced_unknown_is_ignored(self):
        self.replace(COMMAND, "```text", "```text\n*UNKNOWN*: Follows [nosuch].")
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("0 errors, 0 warnings", out)

    def decision_block(self, name):
        """The lines `unknowns` prints for one named decision: its own line and its followers."""
        lines = self.run_script(CHECK, "unknowns", "wrist")[1].splitlines()
        start = next(i for i, l in enumerate(lines) if l.startswith(f"- [{name}] "))
        block = [lines[start]]
        for line in lines[start + 1:]:
            if not line.startswith("    followed at "):
                break
            block.append(line)
        return block

    def test_system_file_may_follow_a_stand_in_decision(self):
        self.append(SYSTEM, "\n*UNKNOWN*: Follows [cross-session-undo]. Consequence: scope shrinks.\n")
        code, out = self.check()
        self.assertEqual(code, 0, out)
        block = self.decision_block("cross-session-undo")
        self.assertTrue(any(l.startswith("    followed at SYSTEM.md:") and l.endswith("(system): scope shrinks.")
                            for l in block), block)

    def test_stand_in_may_follow_a_system_file_decision(self):
        self.replace(TRANSACTION, NO_UNKNOWNS,
                     "*UNKNOWN*: Follows [language]. Consequence: signatures stay untyped.\n")
        code, out = self.check()
        self.assertEqual(code, 0, out)
        block = self.decision_block("language")
        self.assertTrue(any(l.startswith("    followed at undo/transaction.code.wrist.md:") and
                            l.endswith("signatures stay untyped.") for l in block), block)

    def test_system_file_follower_of_an_undeclared_name_is_an_error(self):
        self.append(SYSTEM, "\n*UNKNOWN*: Follows [nosuch]. Consequence: scope shrinks.\n")
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("SYSTEM.md", out)
        self.assertIn("`Follows [nosuch]` matches no declared unknown", out)

    def test_label_words_inside_a_description_do_not_start_clauses(self):
        self.replace(TRANSACTION, NO_UNKNOWNS,
                     "*UNKNOWN*: [workload] Whether the store runs as `kind: StatefulSet` or `kind: Deployment`. "
                     "Kind: blocking. Consequence: manifests differ. Unlocks: the manifest.\n")
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("0 errors, 0 warnings", out)

    def test_upper_case_name_is_an_error(self):
        self.replace(SNAPSHOT, "[cross-session-undo] Whether", "[Cross-Session-Undo] Whether")
        self.assertCheckFails("unknown name [Cross-Session-Undo] must be lower-case letters, digits and hyphens")

    def test_name_with_an_underscore_is_an_error(self):
        self.replace(SYSTEM, "[language]", "[my_language]")
        self.assertCheckFails("unknown name [my_language] must be lower-case letters, digits and hyphens")

    def test_follower_with_an_upper_case_name_is_told_about_the_name(self):
        self.replace(STORE, "Follows [cross-session-undo]", "Follows [Cross-Session-Undo]")
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("unknown name [Cross-Session-Undo] must be lower-case letters, digits and hyphens", out)
        self.assertNotIn("matches no declared unknown", out)

    def test_follows_keyword_may_be_lower_case(self):
        self.replace(STORE, "Follows [cross-session-undo]", "follows [cross-session-undo]")
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("0 errors, 0 warnings", out)

    def test_kind_copied_from_the_template_unchosen_is_an_error(self):
        self.replace(STORE, self.KIND, " Kind: blocking | local.")
        self.assertCheckFails("*UNKNOWN* has `Kind: blocking | local`; it must be blocking or local")

    def test_kind_value_may_carry_markup(self):
        self.replace(STORE, self.KIND, " Kind: **blocking**.")
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("0 errors, 0 warnings", out)

    def test_empty_proposal_counts_as_missing(self):
        self.replace(HISTORY, " Proposed: 1000 steps.", " Proposed: .")
        self.assertCheckFails("*UNKNOWN* with `Kind: local` needs `Proposed:`")

    def test_empty_consequence_warns(self):
        self.replace(STORE, " Consequence: placeholder `.iac`; retention and access cannot be implemented.",
                     " Consequence: .")
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("warning: *UNKNOWN* should state `Consequence:` and `Unlocks:`", out)

    def test_two_markers_on_one_line_warn(self):
        self.replace(TRANSACTION, NO_UNKNOWNS,
                     "*UNKNOWN*: Follows [cross-session-undo]. Consequence: a. "
                     "*UNKNOWN*: Follows [language]. Consequence: b.\n")
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("warning: more than one *UNKNOWN* on this line; write one unknown per line", out)

    def test_extra_clauses_on_a_follower_warn(self):
        self.replace(STORE, "Follows [cross-session-undo]. Consequence:",
                     "Follows [cross-session-undo]. Proposed: keep it. Consequence:")
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("warning: *UNKNOWN* that follows another takes only `Consequence:`; "
                      "move `Proposed:` to the declaration", out)

    def test_invalid_kind_is_a_warning_when_lenient(self):
        self.replace(STORE, self.KIND, " Kind: maybe.")
        code, out = self.check("--lenient")
        self.assertEqual(code, 0, out)
        self.assertIn("warning: *UNKNOWN* has `Kind: maybe`", out)

    def test_local_without_a_proposal_is_a_warning_when_lenient(self):
        self.replace(HISTORY, " Proposed: 1000 steps.", "")
        code, out = self.check("--lenient")
        self.assertEqual(code, 0, out)
        self.assertIn("warning: *UNKNOWN* with `Kind: local` needs `Proposed:`", out)

    def test_every_extra_clause_on_a_follower_is_named(self):
        self.replace(STORE, "Follows [cross-session-undo]. Consequence:",
                     "Follows [cross-session-undo]. Kind: local. Unlocks: nothing. Consequence:")
        _, out = self.check()
        self.assertIn("move `Kind:`, `Unlocks:` to the declaration", out)

    def test_two_markers_warn_on_a_declaration_too(self):
        self.replace(TRANSACTION, NO_UNKNOWNS,
                     "*UNKNOWN*: [a] First. Kind: blocking. Consequence: c. Unlocks: u. "
                     "*UNKNOWN*: [b] Second. Kind: blocking. Consequence: c. Unlocks: u.\n")
        _, out = self.check()
        self.assertIn("warning: more than one *UNKNOWN* on this line", out)

    def test_marker_quoted_in_backticks_is_not_a_second_unknown(self):
        self.replace(TRANSACTION, NO_UNKNOWNS,
                     "*UNKNOWN*: [a] Whether the `*UNKNOWN*:` marker is shown in the UI. Kind: blocking. "
                     "Consequence: c. Unlocks: u.\n")
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("0 errors, 0 warnings", out)

    def test_single_star_with_the_colon_inside_is_not_a_marker(self):
        self.replace(TRANSACTION, NO_UNKNOWNS, "*UNKNOWN:* something. Kind: blocking. Consequence: c. Unlocks: u.\n")
        self.assertCheckFails("no *UNKNOWN* entries and no `Unknowns: none`")


class Roles(TreeCase):
    def test_missing_role_is_an_error(self):
        self.front(TRANSACTION)
        self.assertCheckFails("missing `role:` in front matter")

    def test_missing_role_is_a_warning_when_lenient(self):
        self.front(TRANSACTION)
        code, out = self.check("--lenient")
        self.assertEqual(code, 0, out)
        self.assertIn("warning: missing `role:` in front matter", out)

    def test_role_must_be_one_of_the_three(self):
        self.front(TRANSACTION, "role: helper")
        self.assertCheckFails("front matter role 'helper' must be one of")

    def test_role_is_case_and_space_insensitive(self):
        self.front(TRANSACTION, "role: Product  ")
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("0 errors, 0 warnings", out)

    def test_unclosed_front_matter_reports_a_missing_role(self):
        self.replace(TRANSACTION, FRONT, "---\nrole: product\n")
        self.assertCheckFails("missing `role:` in front matter")

    def test_untested_is_only_for_product(self):
        self.front(TRANSACTION, "role: test", "untested: not needed")
        self.assertCheckFails("`untested:` is only for `role: product` stand-ins")

    def test_untested_needs_a_reason(self):
        self.front(TRANSACTION, "role: product", "untested:")
        self.assertCheckFails("`untested:` needs a reason")

    def test_unit_target_must_be_a_stand_in_in_the_tree(self):
        self.front(TRANSACTION, "role: product", "unit: ./nope.code.wrist.md")
        self.assertCheckFails("`unit:` target is not a stand-in in this tree: ./nope.code.wrist.md")

    def test_unit_target_cannot_be_the_system_file(self):
        self.front(TRANSACTION, "role: product", "unit: ../SYSTEM.md")
        self.assertCheckFails("`unit:` target is not a stand-in in this tree: ../SYSTEM.md")

    def test_unit_target_must_share_the_role(self):
        self.front(COMMAND, "role: test")
        self.front(TRANSACTION, "role: product", "unit: ./command.code.wrist.md")
        self.assertCheckFails("`unit:` target ./command.code.wrist.md has role 'test', not 'product'")

    def test_unit_cannot_chain(self):
        self.front(COMMAND, "role: product", "unit: ./document_target.code.wrist.md")
        self.front(TRANSACTION, "role: product", "unit: ./command.code.wrist.md")
        self.assertCheckFails("`unit:` target ./command.code.wrist.md has a `unit:` of its own")

    def test_unit_cannot_name_itself(self):
        self.front(TRANSACTION, "role: product", "unit: ./transaction.code.wrist.md")
        self.assertCheckFails("`unit:` names this stand-in itself")

    def test_valid_unit_passes(self):
        self.front(TRANSACTION, "role: product", "unit: ./command.code.wrist.md")
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("0 errors, 0 warnings", out)

    def test_kind_override_still_works_beside_role(self):
        moved = "wrist/infra/stack.yml.wrist.md"      # .yml would be read as data without the override
        self.run_script(MV, "wrist", STORE, moved)
        self.assertCheckFails("data file must start with `# data: <name>`")
        self.front(moved, "role: product", "kind: iac")
        code, out = self.check()
        self.assertEqual(code, 0, out)

    def test_invalid_role_is_a_warning_when_lenient(self):
        self.front(TRANSACTION, "role: helper")
        code, out = self.check("--lenient")
        self.assertEqual(code, 0, out)
        self.assertIn("warning: front matter role 'helper' must be one of", out)

    def test_untested_is_not_for_manifests_either(self):
        self.front(TRANSACTION, "role: manifest", "untested: not needed")
        self.assertCheckFails("`untested:` is only for `role: product` stand-ins")

    def test_duplicate_key_warns_and_the_first_is_used(self):
        self.front(TRANSACTION, "role: product", "Role: helper")
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("warning: front matter key 'role' is given twice; the first is used", out)

    def test_unknown_key_warns(self):
        self.front(TRANSACTION, "role: product", "untestd: no need")
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("warning: unknown front matter key 'untestd' (known: kind, role, unit, untested)", out)

    def test_quotes_and_a_trailing_comment_are_ignored(self):
        self.front(TRANSACTION, 'role: "product"   # delivered')
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("0 errors, 0 warnings", out)

    def test_unclosed_front_matter_is_named_as_the_problem(self):
        self.replace(TRANSACTION, FRONT, "---\nrole: product\n")
        self.assertCheckFails("front matter is not closed with `---`")

    def test_rules_in_the_body_are_not_front_matter(self):
        self.replace(TRANSACTION, FRONT, "---\n\nA note above the module.\n\n---\n")
        code, out = self.check()
        self.assertIn("missing `role:` in front matter", out)
        self.assertNotIn("level-1 heading", out)

    def test_product_that_depends_on_a_test_stand_in_warns(self):
        self.front(COMMAND, "role: test")
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("warning: a product stand-in depends on test stand-in undo/command.code.wrist.md", out)

    def test_invalid_kind_is_reported_on_its_own_line(self):
        self.front(SNAPSHOT, "role: product", "kind: sideways")
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("history_snapshot.data.wrist.md:3: error: front matter kind 'sideways'", out)

    def test_byte_order_mark_before_front_matter_is_ignored(self):
        with open(self.path(TRANSACTION), encoding="utf-8") as fh:
            text = fh.read()
        with open(self.path(TRANSACTION), "w", encoding="utf-8") as fh:
            fh.write("﻿" + text)
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("0 errors, 0 warnings", out)


class UntestedUnits(TreeCase):
    """The example is abstract and so exempt; these tests make `command` a concrete Python unit."""

    UNIT = "wrist/src/command.py.wrist.md"
    WARNING = "no test stand-in depends on this unit"

    def setUp(self):
        super().setUp()
        self.run_script(MV, "wrist", COMMAND, self.UNIT)
        # The example's own test stand-in depends on Command; make it product so these tests start uncovered.
        self.replace("wrist/undo/history_test.code.wrist.md", "role: test", "role: product")

    def add_test_stand_in(self, target):
        os.makedirs(self.path("wrist/tests"), exist_ok=True)
        with open(self.path("wrist/tests/command_test.py.wrist.md"), "w", encoding="utf-8") as fh:
            fh.write("---\nrole: test\n---\n"
                     "# module: command_test\n\n"
                     "Round-trip tests for commands.\n\n"
                     "- **Owns:** the command test cases.\n"
                     "- **Access:** run by the test runner only.\n"
                     "- **Required:** always.\n"
                     "- **Failure modes:** none known.\n"
                     f"- **Depends on:** [Command]({target})\n"
                     "- **Referred by:** none known\n"
                     "- **Unknowns:** none\n")
        self.run_script(CHECK, "fix-backlinks", "wrist", "--write")

    def test_concrete_code_unit_without_a_test_warns(self):
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn(f"wrist/src/command.py.wrist.md:1: warning: {self.WARNING}", out)

    def test_abstract_units_do_not_warn(self):
        _, out = self.check()
        self.assertEqual(out.count(self.WARNING), 1, out)

    def test_untested_reason_silences_the_warning(self):
        self.front(self.UNIT, "role: product", "untested: covered by the host's integration tests")
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertNotIn(self.WARNING, out)

    def test_a_test_that_depends_on_the_unit_silences_the_warning(self):
        self.add_test_stand_in("../src/command.py.wrist.md#class-command")
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertNotIn(self.WARNING, out)

    def test_a_test_that_depends_on_another_member_counts(self):
        member = "wrist/src/command_impl.py.wrist.md"
        self.run_script(MV, "wrist", TRANSACTION, member)
        self.front(member, "role: product", "unit: ./command.py.wrist.md")
        self.add_test_stand_in("../src/command_impl.py.wrist.md#class-transaction")
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertNotIn(self.WARNING, out)

    def test_a_product_stand_in_that_depends_on_the_unit_does_not_count(self):
        # history.code depends on command already, and it is product, not test.
        _, out = self.check()
        self.assertIn(self.WARNING, out)

    def test_untested_on_a_non_primary_member_is_an_error(self):
        member = "wrist/src/command_impl.py.wrist.md"
        self.run_script(MV, "wrist", TRANSACTION, member)
        self.front(member, "role: product", "unit: ./command.py.wrist.md", "untested: covered elsewhere")
        self.assertCheckFails("`untested:` belongs on the unit's primary stand-in, src/command.py.wrist.md")


class UntestedUnitRules(MiniTree):
    P, T_ = ["role: product"], ["role: test"]
    CLASS, SYMBOL = ["## class: C"], ["## symbol: S"]

    def test_unit_with_only_symbols_is_not_reported(self):
        self.stand_in("src/consts.py", front=self.P, body=self.SYMBOL)
        self.assertEqual(self.untested(), [])

    def test_data_unit_is_not_reported(self):
        self.stand_in("data/table.json", front=self.P, body=self.CLASS)
        self.assertEqual(self.untested(), [])

    def test_class_in_a_non_primary_member_is_reported_on_the_primary(self):
        self.stand_in("src/a.hpp", front=self.P, body=self.SYMBOL)
        self.stand_in("src/a.cpp", front=["role: product", "unit: ./a.hpp.wrist.md"], body=self.CLASS)
        self.assertEqual(self.untested(), ["src/a.hpp.wrist.md"])

    def test_test_code_that_depends_on_the_unit_covers_it(self):
        self.stand_in("src/a.py", front=self.P, body=self.CLASS)
        self.stand_in("tests/a_test.py", depends=["src/a.py"], front=self.T_)
        self.assertEqual(self.untested(), [])

    def test_test_data_that_depends_on_the_unit_does_not_cover_it(self):
        self.stand_in("tools/gen.py", front=self.P, body=self.CLASS)
        self.stand_in("tests/cases.json", depends=["tools/gen.py"], front=self.T_)
        self.assertEqual(self.untested(), ["tools/gen.py.wrist.md"])

    def test_untested_on_a_non_primary_member_does_not_silence_the_unit(self):
        self.stand_in("src/a.hpp", front=self.P, body=self.CLASS)
        self.stand_in("src/a.cpp", front=["role: product", "unit: ./a.hpp.wrist.md", "untested: later"])
        self.assertEqual(self.untested(), ["src/a.hpp.wrist.md"])


class InferRoles(MiniTree):
    def infer(self, *args):
        return self.run_check("infer-roles", "wrist", *args)

    def test_proposes_roles_from_names_and_folders(self):
        for rel in ("CMakeLists.txt", "src/a.py", "tests/a_test.py", "src/test_b.py", "tests/helper.py",
                    "cmake/Warnings.cmake"):
            self.stand_in(rel)
        _, out = self.infer()
        self.assertIn("CMakeLists.txt.wrist.md:\n  + role: manifest", out)
        self.assertIn("cmake/Warnings.cmake.wrist.md:\n  + role: manifest", out)
        self.assertIn("src/a.py.wrist.md:\n  + role: product", out)
        self.assertIn("tests/a_test.py.wrist.md:\n  + role: test", out)
        self.assertIn("src/test_b.py.wrist.md:\n  + role: test", out)
        self.assertIn("tests/helper.py.wrist.md:\n  + role: test", out)

    def test_dry_run_writes_nothing(self):
        self.stand_in("src/a.py")
        before = self.read("src/a.py")
        _, out = self.infer()
        self.assertIn("(dry run; pass --write to apply)", out)
        self.assertEqual(self.read("src/a.py"), before)

    def test_write_adds_front_matter(self):
        self.stand_in("src/a.py")
        self.infer("--write")
        self.assertTrue(self.read("src/a.py").startswith("---\nrole: product\n---\n# module: a.py\n"))

    def test_write_keeps_existing_front_matter(self):
        self.stand_in("deploy/stack.yml", front=["kind: iac"])
        self.infer("--write")
        self.assertTrue(self.read("deploy/stack.yml").startswith("---\nkind: iac\nrole: product\n---\n"))

    def test_existing_role_is_left_alone(self):
        self.stand_in("src/a.py", front=["role: test"])
        _, out = self.infer()
        self.assertNotIn("src/a.py.wrist.md", out)

    def test_tools_folder_is_unsure_and_never_written(self):
        self.stand_in("tools/gen.py")
        _, out = self.infer("--write")
        self.assertIn("tools/gen.py.wrist.md:\n  ? role: product  (unsure: under tools/, so it may not be delivered)", out)
        self.assertFalse(self.read("tools/gen.py").startswith("---"))

    def test_test_folder_file_that_product_depends_on_is_unsure(self):
        self.stand_in("tests/shared.py")
        self.stand_in("src/a.py", depends=["tests/shared.py"])
        _, out = self.infer("--write")
        self.assertIn("tests/shared.py.wrist.md:\n  ? role: test  "
                      "(unsure: product stand-in src/a.py.wrist.md depends on it)", out)
        self.assertFalse(self.read("tests/shared.py").startswith("---"))

    def test_source_is_paired_with_its_header(self):
        self.stand_in("src/file_map.hpp")
        self.stand_in("src/file_map_posix.cpp", depends=["src/file_map.hpp"])
        _, out = self.infer("--write")
        self.assertIn("src/file_map_posix.cpp.wrist.md:\n  + role: product\n  + unit: ./file_map.hpp.wrist.md", out)
        self.assertTrue(self.read("src/file_map_posix.cpp").startswith(
            "---\nrole: product\nunit: ./file_map.hpp.wrist.md\n---\n"))

    def test_longest_matching_header_wins(self):
        self.stand_in("src/file.hpp")
        self.stand_in("src/file_map.hpp")
        self.stand_in("src/file_map_posix.cpp", depends=["src/file_map.hpp"])
        _, out = self.infer()
        self.assertIn("  + unit: ./file_map.hpp.wrist.md", out)

    def test_header_name_must_end_at_a_word_boundary(self):
        self.stand_in("src/file.hpp")
        self.stand_in("src/filemap.cpp")
        _, out = self.infer()
        self.assertNotIn("unit:", out)

    def test_two_fitting_headers_are_unsure(self):
        for rel in ("src/x.h", "src/x.hpp", "src/x.cpp"):
            self.stand_in(rel)
        _, out = self.infer("--write")
        self.assertIn("  ? unit: ./x.h.wrist.md  (unsure: more than one header fits: x.h.wrist.md, x.hpp.wrist.md)", out)
        self.assertNotIn("unit:", self.read("src/x.cpp"))

    def test_source_is_not_paired_with_a_header_of_another_role(self):
        self.stand_in("src/foo.h")
        self.stand_in("src/foo_test.cc", depends=["src/foo.h"])
        _, out = self.infer()
        self.assertIn("src/foo_test.cc.wrist.md:\n  + role: test\n", out)
        self.assertNotIn("unit:", out)

    def test_same_name_header_is_paired_without_a_link(self):
        self.stand_in("src/x.hpp")
        self.stand_in("src/x.cpp")
        _, out = self.infer()
        self.assertIn("src/x.cpp.wrist.md:\n  + role: product\n  + unit: ./x.hpp.wrist.md", out)

    def test_prefix_match_without_a_link_is_unsure(self):
        self.stand_in("src/file.hpp")
        self.stand_in("src/file_map.cpp")
        _, out = self.infer("--write")
        self.assertIn("  ? unit: ./file.hpp.wrist.md  (unsure: its name only begins with file.hpp, "
                      "and no `Depends on:` link confirms the pairing)", out)
        self.assertNotIn("unit:", self.read("src/file_map.cpp"))

    def test_same_name_header_in_another_folder_is_paired_when_linked(self):
        self.stand_in("include/file_map.hpp")
        self.stand_in("src/file_map.cpp", depends=["include/file_map.hpp"])
        _, out = self.infer()
        self.assertIn("  + unit: ../include/file_map.hpp.wrist.md", out)

    def test_same_name_header_in_another_folder_is_ignored_without_a_link(self):
        self.stand_in("include/file_map.hpp")
        self.stand_in("src/file_map.cpp")
        _, out = self.infer()
        self.assertNotIn("unit:", out)

    def test_header_that_is_itself_in_a_unit_is_unsure(self):
        self.stand_in("src/core.hpp", front=["role: product"])
        self.stand_in("src/a.hpp", front=["role: product", "unit: ./core.hpp.wrist.md"])
        self.stand_in("src/a.cpp")
        _, out = self.infer("--write")
        self.assertIn("  ? unit: ./a.hpp.wrist.md  (unsure: a.hpp is itself part of a unit; "
                      "name that unit's primary instead)", out)
        self.assertNotIn("unit:", self.read("src/a.cpp"))

    def test_unit_is_not_written_while_the_role_is_unsure(self):
        self.stand_in("tools/gen.hpp")
        self.stand_in("tools/gen.cpp")
        self.infer("--write")
        self.assertFalse(self.read("tools/gen.cpp").startswith("---"))

    def test_manifest_names(self):
        names = ["Makefile", "package.json", "pyproject.toml", "Cargo.toml", "go.mod", "go.sum", "pom.xml",
                 "settings.gradle.kts", "requirements-dev.txt", "App.csproj", "All.sln", "lib.gemspec",
                 "tox.ini", "jest.config.js", "vcpkg.json", "cmake/Find.cmake"]
        for name in names:
            self.stand_in(name)
        _, out = self.infer()
        for name in names:
            self.assertIn(f"{name}.wrist.md:\n  + role: manifest", out)

    def test_test_folders_in_any_case(self):
        rels = ["Tests/FooTests.cs", "Test/a.py", "src/__tests__/a.js", "App.Tests/Foo.cs",
                "pkg/testdata/sample.json", "src/test/java/FooTest.java", "web/__mocks__/api.js"]
        for rel in rels:
            self.stand_in(rel)
        _, out = self.infer()
        for rel in rels:
            self.assertIn(f"{rel}.wrist.md:\n  + role: test", out)

    def test_strong_test_names_anywhere(self):
        rels = ["pkg/store_test.go", "src/a.test.ts", "src/a.spec.ts", "src/test_b.py", "conftest.py",
                "lib/foo_spec.rb", "e2e/login.cy.ts"]
        for rel in rels:
            self.stand_in(rel)
        _, out = self.infer()
        for rel in rels:
            self.assertIn(f"{rel}.wrist.md:\n  + role: test", out)

    def test_weak_test_name_outside_a_test_folder_is_unsure(self):
        self.stand_in("src/main/java/LoadTest.java")
        _, out = self.infer("--write")
        self.assertIn("src/main/java/LoadTest.java.wrist.md:\n  ? role: test  (unsure: its name ends in Test, "
                      "Tests or IT, but it is not in a test folder)", out)
        self.assertFalse(self.read("src/main/java/LoadTest.java").startswith("---"))

    def test_spec_folder_without_a_test_name_is_unsure(self):
        self.stand_in("src/spec/openapi.yaml")
        _, out = self.infer()
        self.assertIn("  ? role: test  (unsure: a spec/ folder can hold specifications as well as tests)", out)

    def test_scripts_examples_and_benches_are_unsure(self):
        for rel in ("scripts/deploy.sh", "examples/demo.py", "benches/speed.rs"):
            self.stand_in(rel)
        _, out = self.infer()
        self.assertIn("scripts/deploy.sh.wrist.md:\n  ? role: product  (unsure: under scripts/", out)
        self.assertIn("examples/demo.py.wrist.md:\n  ? role: product  (unsure: under examples/", out)
        self.assertIn("benches/speed.rs.wrist.md:\n  ? role: product  (unsure: under benches/", out)

    def test_test_name_under_tools_is_still_unsure(self):
        self.stand_in("tools/test_gen.py")
        _, out = self.infer()
        self.assertIn("tools/test_gen.py.wrist.md:\n  ? role: test  (unsure: under tools/", out)

    def malformed(self, text):
        path = self.file("src/a.py")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        _, out = self.infer("--write")
        self.assertIn("src/a.py.wrist.md:\n  ? front matter  (unsure: it opens with `---` and is not closed; "
                      "fix it by hand)", out)
        self.assertEqual(self.read("src/a.py"), text)

    def test_unclosed_front_matter_is_never_written_into(self):
        self.malformed("---\nrole: test\nuntested: nope\n# module: a\n")

    def test_unclosed_front_matter_with_a_later_rule_is_never_written_into(self):
        self.malformed("---\nrole: test\n# module: a\n\nProse.\n\n---\n\nMore.\n")

    def test_body_that_opens_with_a_rule_is_never_written_into(self):
        self.malformed("---\n\nA note.\n\n---\n# module: a\n")

    def test_summary_counts_writes_and_unsure(self):
        self.stand_in("src/a.py")
        self.stand_in("tools/gen.py")
        _, out = self.infer()
        self.assertIn("1 to write, 1 unsure (never written; set those by hand)", out)

    def test_second_write_changes_nothing(self):
        self.stand_in("src/file_map.hpp")
        self.stand_in("src/file_map_posix.cpp", depends=["src/file_map.hpp"])
        self.infer("--write")
        after_first = self.read("src/file_map_posix.cpp")
        _, out = self.infer("--write")
        self.assertIn("Nothing to infer.", out)
        self.assertEqual(self.read("src/file_map_posix.cpp"), after_first)


class InferRolesOnTheExample(TreeCase):
    def test_stripped_example_passes_check_again_after_write(self):
        for dp, _, fns in os.walk(self.path("wrist")):
            for fn in fns:
                if fn.endswith(".wrist.md"):
                    path = os.path.join(dp, fn)
                    with open(path, encoding="utf-8") as fh:
                        text = fh.read()
                    self.assertTrue(text.startswith("---\n"), path)
                    with open(path, "w", encoding="utf-8") as fh:
                        fh.write(text.split("---\n", 2)[2])
        self.assertEqual(self.check()[0], 1)
        _, out = self.run_script(CHECK, "infer-roles", "wrist", "--write")
        self.assertIn("undo/history_test.code.wrist.md:\n  + role: test", out)
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("0 errors, 0 warnings", out)


class Batches(MiniTree):
    P = ["role: product"]

    def setUp(self):
        super().setUp()
        self.stand_in("src/err.hpp", front=self.P)
        self.stand_in("src/fm.hpp", depends=["src/err.hpp"], front=self.P)
        self.stand_in("src/fm_posix.cpp", depends=["src/fm.hpp", "src/err.hpp"],
                      front=["role: product", "unit: ./fm.hpp.wrist.md"])
        self.stand_in("tests/fm_test.cpp", depends=["src/fm.hpp"], front=["role: test"])
        self.stand_in("CMakeLists.txt", depends=["src/fm_posix.cpp", "tests/fm_test.cpp"], front=["role: manifest"])

    def batches(self, *args):
        return self.run_check("batches", "wrist", *args)

    def batch_of(self, out, path):
        number = None
        for line in out.splitlines():
            if line.startswith("Batch "):
                number = int(line.split()[1].rstrip(":"))
            elif line.strip().startswith(path):
                return number
        self.fail(f"{path} not in:\n{out}")

    def test_unit_members_share_one_line(self):
        _, out = self.batches()
        self.assertIn("  src/fm.hpp  (+ src/fm_posix.cpp)", out)
        self.assertNotIn("cycle", out)

    def test_manifests_are_listed_first_and_not_batched(self):
        code, out = self.batches()
        self.assertEqual(code, 0, out)
        lines = out.splitlines()
        self.assertEqual(lines[0], "Manifests (create with batch 1, extend with every batch):")
        self.assertEqual(lines[1], "  CMakeLists.txt")
        self.assertEqual(out.count("CMakeLists.txt"), 1)

    def test_dependencies_come_in_earlier_batches(self):
        _, out = self.batches()
        self.assertEqual(self.batch_of(out, "src/err.hpp"), 1)
        self.assertEqual(self.batch_of(out, "src/fm.hpp"), 2)
        self.assertEqual(self.batch_of(out, "tests/fm_test.cpp"), 3)

    def test_test_units_are_tagged(self):
        _, out = self.batches()
        self.assertIn("  tests/fm_test.cpp  [test]", out)

    def test_cycle_shares_a_batch_and_is_flagged(self):
        self.stand_in("src/a.hpp", depends=["src/b.hpp"], front=self.P)
        self.stand_in("src/b.hpp", depends=["src/a.hpp"], front=self.P)
        _, out = self.batches()
        self.assertEqual(self.batch_of(out, "src/a.hpp"), self.batch_of(out, "src/b.hpp"))
        self.assertIn("  src/a.hpp  [cycle]", out)
        self.assertIn("  src/b.hpp  [cycle]", out)

    def test_json_shape(self):
        _, out = self.batches("--json")
        data = json.loads(out)
        self.assertEqual(data["manifests"], ["CMakeLists.txt"])
        self.assertEqual([b["batch"] for b in data["batches"]], [1, 2, 3])
        unit = data["batches"][1]["units"][0]
        self.assertEqual(unit, {"unit": "src/fm.hpp", "files": ["src/fm.hpp", "src/fm_posix.cpp"],
                                "role": "product", "cycle": False, "abstract": False, "unknowns": 0,
                                "depends_on": ["src/err.hpp"], "depends_on_manifests": []})
        self.assertEqual(data["ignored_units"], [])

    def test_tree_without_roles_is_batched_as_product(self):
        for rel in ("src/err.hpp", "src/fm.hpp", "src/fm_posix.cpp", "tests/fm_test.cpp", "CMakeLists.txt"):
            text = self.read(rel)
            with open(self.file(rel), "w", encoding="utf-8") as fh:
                fh.write(text.split("---\n", 2)[2])
        code, out = self.batches("--json")
        self.assertEqual(code, 0, out)
        data = json.loads(out)
        units = [u for b in data["batches"] for u in b["units"]]
        self.assertEqual(data["manifests"], [])
        self.assertEqual(sorted(u["unit"] for u in units),
                         ["CMakeLists.txt", "src/err.hpp", "src/fm.hpp", "src/fm_posix.cpp", "tests/fm_test.cpp"])
        self.assertEqual({u["role"] for u in units}, {"product"})

    def test_a_dependency_of_a_non_primary_member_orders_the_unit(self):
        self.stand_in("src/late.hpp", depends=["src/fm.hpp"], front=self.P)
        self.stand_in("src/z.hpp", front=self.P)
        self.stand_in("src/z_impl.cpp", depends=["src/late.hpp"], front=["role: product", "unit: ./z.hpp.wrist.md"])
        _, out = self.batches()
        self.assertEqual(self.batch_of(out, "src/z.hpp"), self.batch_of(out, "src/late.hpp") + 1)

    def test_a_dependency_on_a_manifest_does_not_order_the_unit(self):
        self.stand_in("src/gen.hpp", depends=["CMakeLists.txt"], front=self.P)
        _, out = self.batches()
        self.assertEqual(self.batch_of(out, "src/gen.hpp"), 1)
        self.assertEqual(out.count("CMakeLists.txt"), 1)

    def test_empty_tree_says_so(self):
        os.makedirs(os.path.join(self.dir, "empty"))
        code, out = self.run_check("batches", "empty")
        self.assertEqual(code, 0, out)
        self.assertEqual(out.strip(), "No stand-ins.")

    def test_invalid_unit_value_is_noted(self):
        self.stand_in("src/q.cpp", front=["role: product", "unit: ./nope.hpp.wrist.md"])
        _, out = self.batches()
        self.assertIn("note: 1 `unit:` value ignored because it is not valid; `check` explains why:\n"
                      "  src/q.cpp.wrist.md", out)
        self.assertEqual(json.loads(self.batches("--json")[1])["ignored_units"], ["src/q.cpp.wrist.md"])

    def test_manifest_dependencies_are_listed_in_json(self):
        self.stand_in("src/gen.hpp", depends=["CMakeLists.txt"], front=self.P)
        data = json.loads(self.batches("--json")[1])
        unit = next(u for b in data["batches"] for u in b["units"] if u["unit"] == "src/gen.hpp")
        self.assertEqual(unit["depends_on_manifests"], ["CMakeLists.txt"])
        self.assertEqual(unit["depends_on"], [])


class BatchesOnTheExample(TreeCase):
    def test_example_is_batched_with_dependencies_first(self):
        code, out = self.run_script(CHECK, "batches", "wrist")
        self.assertEqual(code, 0, out)
        self.assertLess(out.index("undo/command.code"), out.index("undo/transaction.code"))
        self.assertIn("[ABSTRACT]", out)

    def test_example_shows_a_test_stand_in(self):
        _, out = self.run_script(CHECK, "batches", "wrist")
        self.assertIn("  undo/history_test.code  [test] [ABSTRACT]", out)


class FixBacklinks(TreeCase):
    def test_write_restores_a_deleted_backlink(self):
        self.replace(COMMAND, BACKLINK, "")
        self.assertEqual(self.check()[0], 1)
        self.run_script(CHECK, "fix-backlinks", "wrist", "--write")
        code, out = self.check()
        self.assertEqual(code, 0, out)

    def test_dry_run_changes_nothing(self):
        self.replace(COMMAND, BACKLINK, "")
        _, out = self.run_script(CHECK, "fix-backlinks", "wrist")
        self.assertIn("dry run", out)
        self.assertEqual(self.check()[0], 1)


class Order(TreeCase):
    def test_cycle_is_flagged(self):
        self.replace(COMMAND, "- **Depends on:** [DocumentTarget](./document_target.code.wrist.md#class-documenttarget)\n",
                     "- **Depends on:** [DocumentTarget](./document_target.code.wrist.md#class-documenttarget)\n"
                     "- **Depends on:** [Transaction](./transaction.code.wrist.md#class-transaction)\n")
        self.run_script(CHECK, "fix-backlinks", "wrist", "--write")
        code, out = self.run_script(CHECK, "order", "wrist")
        self.assertEqual(code, 0, out)
        self.assertIn("cycle", out)

    def test_dependencies_come_first(self):
        _, out = self.run_script(CHECK, "order", "wrist")
        self.assertLess(out.index("undo/command.code"), out.index("undo/transaction.code"))


class Move(TreeCase):
    def test_moving_a_file_keeps_the_tree_valid(self):
        code, out = self.run_script(MV, "wrist", COMMAND, "wrist/src/undo/command.ts.wrist.md")
        self.assertEqual(code, 0, out)
        self.assertTrue(os.path.exists(self.path("wrist/src/undo/command.ts.wrist.md")))
        code, out = self.check()
        self.assertEqual(code, 0, out)

    def test_moving_a_directory_keeps_the_tree_valid(self):
        code, out = self.run_script(MV, "wrist", "wrist/undo", "wrist/src/core/undo")
        self.assertEqual(code, 0, out)
        code, out = self.check()
        self.assertEqual(code, 0, out)

    def test_dry_run_moves_nothing(self):
        self.run_script(MV, "wrist", COMMAND, "wrist/src/undo/command.ts.wrist.md", "--dry-run")
        self.assertTrue(os.path.exists(self.path(COMMAND)))


class MoveUnits(MiniTree):
    def setUp(self):
        super().setUp()
        self.stand_in("src/fm.hpp", front=["role: product"])
        self.stand_in("src/fm_posix.cpp", depends=["src/fm.hpp"], front=["role: product", "unit: ./fm.hpp.wrist.md"])

    def move(self, old, new):
        proc = subprocess.run([sys.executable, MV, "wrist", old, new], cwd=self.dir, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_moving_the_header_updates_the_source(self):
        self.move("wrist/src/fm.hpp.wrist.md", "wrist/include/fm.hpp.wrist.md")
        self.assertIn("unit: ../include/fm.hpp.wrist.md\n", self.read("src/fm_posix.cpp"))

    def test_moving_the_source_updates_its_own_unit_path(self):
        self.move("wrist/src/fm_posix.cpp.wrist.md", "wrist/src/posix/fm_posix.cpp.wrist.md")
        self.assertIn("unit: ../fm.hpp.wrist.md\n", self.read("src/posix/fm_posix.cpp"))

    def test_moving_both_together_leaves_the_path_alone(self):
        self.move("wrist/src", "wrist/lib")
        self.assertIn("unit: ./fm.hpp.wrist.md\n", self.read("lib/fm_posix.cpp"))

    def test_unit_key_in_any_case_is_rewritten(self):
        text = self.read("src/fm_posix.cpp").replace("unit: ./fm.hpp.wrist.md", "Unit: ./fm.hpp.wrist.md")
        with open(self.file("src/fm_posix.cpp"), "w", encoding="utf-8") as fh:
            fh.write(text)
        self.move("wrist/src/fm.hpp.wrist.md", "wrist/include/fm.hpp.wrist.md")
        self.assertIn("Unit: ../include/fm.hpp.wrist.md\n", self.read("src/fm_posix.cpp"))

    def test_link_inside_a_front_matter_value_is_rewritten(self):
        self.stand_in("src/other.py", front=["role: product", "untested: covered through [fm](./fm.hpp.wrist.md)"])
        self.move("wrist/src/fm.hpp.wrist.md", "wrist/include/fm.hpp.wrist.md")
        self.assertIn("untested: covered through [fm](../include/fm.hpp.wrist.md)\n", self.read("src/other.py"))

    def test_links_under_a_rule_at_the_top_of_a_file_are_rewritten(self):
        notes = os.path.join(self.dir, "wrist", "NOTES.md")
        with open(notes, "w", encoding="utf-8") as fh:
            fh.write("---\n\nSee [fm](./src/fm.hpp.wrist.md).\n\n---\n")
        self.move("wrist/src/fm.hpp.wrist.md", "wrist/include/fm.hpp.wrist.md")
        with open(notes, encoding="utf-8") as fh:
            self.assertIn("See [fm](./include/fm.hpp.wrist.md).", fh.read())

    def test_unit_like_text_in_the_body_is_not_touched(self):
        with open(self.file("src/fm_posix.cpp"), "a", encoding="utf-8") as fh:
            fh.write("unit: ./fm.hpp.wrist.md\n")
        self.move("wrist/src/fm.hpp.wrist.md", "wrist/include/fm.hpp.wrist.md")
        self.assertTrue(self.read("src/fm_posix.cpp").endswith("unit: ./fm.hpp.wrist.md\n"))


class CodeCase(TreeCase):
    """`command` becomes a concrete Python stand-in with an implemented file beside the tree."""

    UNIT = "wrist/src/command.py.wrist.md"
    CODE = "src/command.py"
    HEADER = "# Spec: wrist/src/command.py.wrist.md\n"
    BODY = ("class Command:\n    def apply(self): ...\n    def revert(self): ...\n"
            "    def merge_with(self, other): ...\n    def describe(self): ...\n")

    def setUp(self):
        super().setUp()
        self.run_script(MV, "wrist", COMMAND, self.UNIT)
        os.makedirs(self.path("src"))
        self.write_code(self.HEADER + self.BODY)

    def write_code(self, text, rel=None):
        with open(self.path(rel or self.CODE), "w", encoding="utf-8") as fh:
            fh.write(text)

    def read_code(self):
        with open(self.path(self.CODE), encoding="utf-8") as fh:
            return fh.read()

    def stamp(self, *args):
        return self.run_script(CHECK, "stamp", "wrist", "--root", ".", *args)


class Stamp(CodeCase):
    STAMPED = r"^# Spec: wrist/src/command\.py\.wrist\.md @ [0-9a-f]{8}\n"

    def test_stamp_adds_a_hash_to_the_header(self):
        code, out = self.stamp(self.CODE)
        self.assertEqual(code, 0, out)
        self.assertRegex(self.read_code(), self.STAMPED)
        self.assertTrue(self.read_code().endswith(self.BODY))

    def test_stamp_needs_paths_or_all(self):
        code, out = self.stamp()
        self.assertNotEqual(code, 0)
        self.assertIn("stamp needs the implemented files to stamp, or --all", out)

    def test_stamp_keeps_the_rest_of_the_header_line(self):
        self.write_code("/* Spec: wrist/src/command.py.wrist.md */\n" + self.BODY)
        self.stamp(self.CODE)
        self.assertRegex(self.read_code(), r"^/\* Spec: wrist/src/command\.py\.wrist\.md @ [0-9a-f]{8} \*/\n")

    def test_stamp_replaces_an_old_hash_and_then_reports_it_current(self):
        self.write_code("# Spec: wrist/src/command.py.wrist.md @ 00000000\n" + self.BODY)
        _, first = self.stamp(self.CODE)
        self.assertIn("stamped src/command.py @ ", first)
        self.assertNotIn("@ 00000000", self.read_code())
        _, second = self.stamp(self.CODE)
        self.assertIn("0 stamped, 1 already current", second)

    def test_named_file_without_a_header_fails(self):
        self.write_code(self.BODY)
        code, out = self.stamp(self.CODE)
        self.assertEqual(code, 1, out)
        self.assertIn("src/command.py: no `Spec: wrist/src/command.py.wrist.md` header in its first 10 lines", out)
        self.assertEqual(self.read_code(), self.BODY)

    def test_header_past_the_tenth_line_is_not_found(self):
        self.write_code("\n" * 10 + self.HEADER + self.BODY)
        code, out = self.stamp(self.CODE)
        self.assertEqual(code, 1, out)
        self.assertIn("no `Spec: wrist/src/command.py.wrist.md` header", out)

    def test_all_reports_a_file_without_a_header_and_still_succeeds(self):
        self.write_code(self.BODY)
        code, out = self.stamp("--all")
        self.assertEqual(code, 0, out)
        self.assertIn("src/command.py: no `Spec: wrist/src/command.py.wrist.md` header", out)

    def test_path_with_no_stand_in_fails(self):
        self.write_code("# anything\n", rel="src/orphan.py")
        code, out = self.stamp("src/orphan.py")
        self.assertEqual(code, 1, out)
        self.assertIn("src/orphan.py: no stand-in in this tree", out)

    def test_new_backlink_does_not_change_the_hash(self):
        self.stamp(self.CODE)
        self.append(self.UNIT, "- **Referred by:** none known\n")
        _, out = self.stamp(self.CODE)
        self.assertIn("0 stamped, 1 already current", out)

    def test_blank_lines_and_trailing_spaces_do_not_change_the_hash(self):
        self.stamp(self.CODE)
        self.replace(self.UNIT, "## class: Command\n", "## class: Command   \n\n\n")
        _, out = self.stamp(self.CODE)
        self.assertIn("0 stamped, 1 already current", out)

    def test_changed_contract_changes_the_hash(self):
        self.stamp(self.CODE)
        before = self.read_code()
        self.replace(self.UNIT, "- **Returns:** success or failure.", "- **Returns:** nothing.")
        _, out = self.stamp(self.CODE)
        self.assertIn("1 stamped, 0 already current", out)
        self.assertNotEqual(self.read_code(), before)

    BLOCK = ("- **Referred by:**\n"
             "  - [Transaction](./undo/transaction.code.wrist.md#class-transaction)\n"
             "  - [UndoHistory](./undo/history.code.wrist.md#class-undohistory)\n")

    def test_block_form_backlinks_do_not_change_the_hash(self):
        self.stamp(self.CODE)
        self.replace(self.UNIT, "- **Unknowns:** none\n", self.BLOCK + "- **Unknowns:** none\n")
        _, out = self.stamp(self.CODE)
        self.assertIn("0 stamped, 1 already current", out)

    def test_field_after_block_form_backlinks_still_counts(self):
        self.replace(self.UNIT, "- **Depends on:** [DocumentTarget]",
                     self.BLOCK + "- **Depends on:** [DocumentTarget]")
        self.stamp(self.CODE)
        self.replace(self.UNIT, "- **Depends on:** [DocumentTarget]", "- **Depends on:** [Target]")
        _, out = self.stamp(self.CODE)
        self.assertIn("1 stamped, 0 already current", out)

    def test_rewrapped_sentence_does_not_change_the_hash(self):
        self.stamp(self.CODE)
        self.replace(self.UNIT, "- **Required:** always.", "- **Required:**\n    always.")
        _, out = self.stamp(self.CODE)
        self.assertIn("0 stamped, 1 already current", out)

    def test_backlink_looking_line_inside_a_fence_counts(self):
        self.stamp(self.CODE)
        self.replace(self.UNIT, "```text", "```text\n- **Referred by:** an example, not a backlink")
        _, out = self.stamp(self.CODE)
        self.assertIn("1 stamped, 0 already current", out)

    def raw(self, data=None):
        if data is None:
            with open(self.path(self.CODE), "rb") as fh:
                return fh.read()
        with open(self.path(self.CODE), "wb") as fh:
            fh.write(data)

    def test_stamp_keeps_carriage_returns(self):
        self.raw(b"# Spec: wrist/src/command.py.wrist.md\r\nclass Command:\r\n    pass\r\n")
        self.stamp(self.CODE)
        data = self.raw()
        self.assertRegex(data, rb"^# Spec: wrist/src/command\.py\.wrist\.md @ [0-9a-f]{8}\r\nclass Command:\r\n    pass\r\n$")

    def test_stamp_keeps_a_missing_final_newline_and_other_bytes(self):
        self.raw(b"# Spec: wrist/src/command.py.wrist.md\n# \xa9 someone\nclass Command: ...")
        code, out = self.stamp(self.CODE)
        self.assertEqual(code, 0, out)
        self.assertTrue(self.raw().endswith(b"\n# \xa9 someone\nclass Command: ..."))

    def test_header_on_the_tenth_line_is_found_and_rewritten_there(self):
        self.write_code("#\n" * 9 + self.HEADER + self.BODY)
        code, out = self.stamp(self.CODE)
        self.assertEqual(code, 0, out)
        lines = self.read_code().splitlines()
        self.assertEqual(lines[0], "#")
        self.assertRegex(lines[9], r"^# Spec: wrist/src/command\.py\.wrist\.md @ [0-9a-f]{8}$")

    def test_only_the_first_spec_on_the_line_is_stamped(self):
        self.write_code("# Spec: wrist/src/command.py.wrist.md (not Spec: wrist/other.wrist.md)\n" + self.BODY)
        self.stamp(self.CODE)
        self.assertRegex(self.read_code(),
                         r"^# Spec: wrist/src/command\.py\.wrist\.md @ [0-9a-f]{8} \(not Spec: wrist/other\.wrist\.md\)\n")

    def test_header_naming_another_stand_in_is_not_stamped(self):
        text = "# Spec: wrist/src/other.py.wrist.md\n" + self.BODY
        self.write_code(text)
        code, out = self.stamp(self.CODE)
        self.assertEqual(code, 1, out)
        self.assertIn("src/command.py: its Spec: header names wrist/src/other.py.wrist.md, "
                      "not wrist/src/command.py.wrist.md", out)
        self.assertEqual(self.read_code(), text)

    def test_over_long_or_upper_case_hash_is_replaced_whole(self):
        self.write_code("# Spec: wrist/src/command.py.wrist.md @ ABCDEF123\n" + self.BODY)
        self.stamp(self.CODE)
        self.assertRegex(self.read_code(), r"^# Spec: wrist/src/command\.py\.wrist\.md @ [0-9a-f]{8}\n")

    def test_read_only_file_is_reported_not_a_crash(self):
        os.chmod(self.path(self.CODE), 0o444)
        self.addCleanup(os.chmod, self.path(self.CODE), 0o644)
        if os.access(self.path(self.CODE), os.W_OK):
            self.skipTest("running as a user who can write read-only files")
        code, out = self.stamp(self.CODE)
        self.assertEqual(code, 1, out)
        self.assertIn("src/command.py: cannot be rewritten", out)
        self.assertNotIn("Traceback", out)

    def test_paths_and_all_together_are_refused(self):
        code, out = self.stamp("--all", self.CODE)
        self.assertNotEqual(code, 0)
        self.assertIn("give the files to stamp or --all, not both", out)

    def test_non_code_file_is_never_stamped(self):
        self.run_script(MV, "wrist", STORE, "wrist/infra/main.tf.wrist.md")
        os.makedirs(self.path("infra"))
        text = "# Spec: wrist/infra/main.tf.wrist.md\n"
        self.write_code(text, rel="infra/main.tf")
        code, out = self.stamp("infra/main.tf")
        self.assertEqual(code, 1, out)
        self.assertIn("infra/main.tf: only code stand-ins that are not generated carry a stamp", out)
        self.stamp("--all")
        with open(self.path("infra/main.tf"), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), text)


class Status(CodeCase):
    """`command` is implemented and stamped; `transaction` is concrete but not implemented."""

    def setUp(self):
        super().setUp()
        self.run_script(MV, "wrist", TRANSACTION, "wrist/src/transaction.py.wrist.md")
        self.write_code("# placeholder\n", rel="src/orphan.py")
        self.stamp(self.CODE)

    def section(self, title):
        lines = self.run_script(CHECK, "status", "wrist", "--root", ".")[1].splitlines()
        start = next(i for i, l in enumerate(lines) if l.startswith(title))
        body = []
        for line in lines[start + 1:]:
            if not line.startswith("  "):
                break
            body.append(line.strip())
        return lines[start], body

    def test_stamped_file_is_implemented(self):
        self.assertEqual(self.section("Implemented"), ("Implemented (1):", ["src/command.py"]))
        self.assertEqual(self.section("Stale")[1], [])
        self.assertEqual(self.section("Unstamped")[1], [])

    def test_missing_concrete_file_is_pending(self):
        self.assertEqual(self.section("Pending"), ("Pending (1):", ["src/transaction.py"]))

    def test_abstract_stand_ins_are_listed_apart_from_pending(self):
        head, body = self.section("Abstract")
        self.assertEqual(head, "Abstract, adapt before implementing (6):")
        self.assertIn("infra/history_store.iac  [2 UNKNOWN]", body)

    def test_code_with_no_stand_in_is_reported(self):
        self.assertEqual(self.section("Code/IaC files with no stand-in")[1], ["src/orphan.py"])

    def test_changed_stand_in_makes_its_code_stale(self):
        self.replace(self.UNIT, "- **Returns:** success or failure.", "- **Returns:** nothing.")
        self.assertEqual(self.section("Stale"),
                         ("Stale, stand-in changed since stamped (1):", ["src/command.py"]))
        self.assertEqual(self.section("Implemented")[1], [])

    def test_new_backlink_does_not_make_code_stale(self):
        self.append(self.UNIT, "- **Referred by:** none known\n")
        self.assertEqual(self.section("Stale")[1], [])

    def test_reflowed_stand_in_does_not_make_code_stale(self):
        self.replace(self.UNIT, "## class: Command\n", "## class: Command   \n\n\n")
        self.assertEqual(self.section("Stale")[1], [])

    def test_file_without_a_header_is_unstamped(self):
        self.write_code(self.BODY)
        self.assertEqual(self.section("Unstamped"), ("Unstamped (1):", ["src/command.py  (no Spec: header)"]))

    def test_header_without_a_hash_is_unstamped(self):
        self.write_code(self.HEADER + self.BODY)
        self.assertEqual(self.section("Unstamped")[1], ["src/command.py  (no hash; run stamp)"])

    def test_header_naming_another_stand_in_is_unstamped(self):
        self.write_code("# Spec: wrist/src/other.py.wrist.md @ 00000000\n" + self.BODY)
        self.assertEqual(self.section("Unstamped")[1],
                         ["src/command.py  (Spec: header names wrist/src/other.py.wrist.md)"])

    def test_all_names_present_lists_nothing(self):
        self.assertEqual(self.section("Names not found in code"), ("Names not found in code (0):", []))

    def test_names_missing_from_the_code_are_listed(self):
        self.write_code(self.HEADER + "class Command:\n    def apply(self): ...\n")
        self.assertEqual(self.section("Names not found in code"),
                         ("Names not found in code (3):",
                          ["src/command.py: function revert", "src/command.py: function merge_with",
                           "src/command.py: function describe"]))

    def test_a_name_inside_a_longer_identifier_does_not_count(self):
        self.write_code(self.HEADER + "class Command:\n    def reapply(self): ...\n    def revert(self): ...\n"
                        "    def merge_with(self, o): ...\n    def describe_all(self): ...\n")
        self.assertEqual(self.section("Names not found in code")[1],
                         ["src/command.py: function apply", "src/command.py: function describe"])

    def test_generated_code_needs_no_stamp_and_no_names(self):
        self.replace(self.UNIT, "- **Owns:** the `Command` contract.\n",
                     "- **Owns:** the `Command` contract.\n- **Source:** generated by a tool\n")
        self.write_code("X = 1\n")
        self.assertEqual(self.section("Implemented")[1], ["src/command.py  (generated)"])
        self.assertEqual(self.section("Names not found in code")[1], [])

    def test_data_file_is_implemented_without_a_stamp(self):
        self.run_script(MV, "wrist", SNAPSHOT, "wrist/data/history.json.wrist.md")
        os.makedirs(self.path("data"))
        self.write_code("{}\n", rel="data/history.json")
        self.assertIn("data/history.json", self.section("Implemented")[1])

    def test_header_on_line_ten_counts_and_on_line_eleven_does_not(self):
        self.write_code("#\n" * 9 + self.HEADER + self.BODY)
        self.assertEqual(self.section("Unstamped")[1], ["src/command.py  (no hash; run stamp)"])
        self.write_code("#\n" * 10 + self.HEADER + self.BODY)
        self.assertEqual(self.section("Unstamped")[1], ["src/command.py  (no Spec: header)"])

    def test_rewrapped_stand_in_does_not_make_code_stale(self):
        self.replace(self.UNIT, "- **Required:** always.", "- **Required:**\n    always.")
        self.assertEqual(self.section("Stale")[1], [])

    def test_infrastructure_file_is_implemented_without_a_stamp(self):
        self.run_script(MV, "wrist", STORE, "wrist/infra/main.tf.wrist.md")
        os.makedirs(self.path("infra"))
        self.write_code("resource {}\n", rel="infra/main.tf")
        self.assertIn("infra/main.tf", self.section("Implemented")[1])

    def test_source_field_that_only_mentions_generation_is_not_an_exemption(self):
        self.replace(self.UNIT, "- **Owns:** the `Command` contract.\n",
                     "- **Owns:** the `Command` contract.\n- **Source:** hand-written, never generated\n")
        self.write_code("X = 1\n")
        self.assertEqual(self.section("Unstamped")[1], ["src/command.py  (no Spec: header)"])

    def test_source_generated_below_file_level_is_not_an_exemption(self):
        self.replace(self.UNIT, "### function: describe\n", "### function: describe\n\n- **Source:** generated ids\n")
        self.write_code("X = 1\n")
        self.assertEqual(self.section("Unstamped")[1], ["src/command.py  (no Spec: header)"])

    def test_stale_primary_lists_the_rest_of_its_unit(self):
        member = "wrist/src/command_impl.py.wrist.md"
        self.run_script(MV, "wrist", "wrist/src/transaction.py.wrist.md", member)
        self.front(member, "role: product", "unit: ./command.py.wrist.md")
        self.replace(self.UNIT, "- **Returns:** success or failure.", "- **Returns:** nothing.")
        self.assertEqual(self.section("Stale")[1], ["src/command.py  (unit: also src/command_impl.py)"])

    def test_unreadable_file_is_listed_and_status_still_succeeds(self):
        os.chmod(self.path(self.CODE), 0o000)
        self.addCleanup(os.chmod, self.path(self.CODE), 0o644)
        if os.access(self.path(self.CODE), os.R_OK):
            self.skipTest("running as a user who can read unreadable files")
        code, out = self.run_script(CHECK, "status", "wrist", "--root", ".")
        self.assertEqual(code, 0, out)
        self.assertIn("  src/command.py  (cannot be read)", out)

    def test_directory_at_the_implemented_path_is_listed(self):
        os.remove(self.path(self.CODE))
        os.makedirs(self.path(self.CODE))
        code, out = self.run_script(CHECK, "status", "wrist", "--root", ".")
        self.assertEqual(code, 0, out)
        self.assertIn("  src/command.py  (cannot be read)", out)

    def test_non_utf8_bytes_do_not_stop_status(self):
        with open(self.path(self.CODE), "ab") as fh:
            fh.write(b"# \xa9 someone\n")
        self.assertEqual(self.section("Implemented")[1], ["src/command.py"])

    def test_heading_with_a_signature_or_backticks_is_matched_by_its_name(self):
        self.replace(self.UNIT, "### function: describe\n", "### function: `describe`(self) -> str\n")
        self.replace(self.UNIT, "## class: Command\n", "## class: `Command` (abstract)\n")
        self.assertEqual(self.section("Names not found in code")[1], [])

    def test_qualified_heading_is_matched_by_its_last_part(self):
        self.replace(self.UNIT, "### function: describe\n", "### function: Command::describe\n")
        self.assertEqual(self.section("Names not found in code")[1], [])

    def test_missing_class_and_symbol_are_listed(self):
        self.append(self.UNIT, "\n## symbol: MAX_DEPTH\n\n- **Access:** public.\n")
        self.write_code(self.HEADER + "def apply(): ...\ndef revert(): ...\ndef merge_with(): ...\ndef describe(): ...\n")
        self.assertEqual(self.section("Names not found in code")[1],
                         ["src/command.py: class Command", "src/command.py: symbol MAX_DEPTH"])


if __name__ == "__main__":
    unittest.main()
