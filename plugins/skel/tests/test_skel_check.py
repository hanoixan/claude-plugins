"""Tests for skel_check.py and skel_mv.py.

Each test copies the bundled undo-system example into a temporary directory,
breaks it in one way, and runs the script as a user would.

Run from the repository root:

    python3 -m unittest discover -s plugins/skel/tests
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

SKILL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "skills", "skel")
EXAMPLE = os.path.join(SKILL, "assets", "examples", "undo-system", "skel")
CHECK = os.path.join(SKILL, "scripts", "skel_check.py")
MV = os.path.join(SKILL, "scripts", "skel_mv.py")

COMMAND = "skel/undo/command.code.skel.md"
TRANSACTION = "skel/undo/transaction.code.skel.md"
HISTORY = "skel/undo/history.code.skel.md"
STORE = "skel/infra/history_store.iac.skel.md"
SYSTEM = "skel/SYSTEM.md"
SNAPSHOT = "skel/undo/history_snapshot.data.skel.md"
NO_UNKNOWNS = "- **Unknowns:** none\n"

BACKLINK = "- **Referred by:** [Transaction](./transaction.code.skel.md#class-transaction)\n"
COMMAND_LINK = "./command.code.skel.md#class-command"


class TreeCase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="skel-test-")
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        shutil.copytree(EXAMPLE, os.path.join(self.dir, "skel"))

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

    def run_script(self, script, *args):
        proc = subprocess.run([sys.executable, script, *args], cwd=self.dir,
                              capture_output=True, text=True)
        return proc.returncode, proc.stdout + proc.stderr

    def check(self, *args):
        return self.run_script(CHECK, "check", "skel", *args)

    def assertCheckFails(self, fragment):
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("error", out)
        self.assertIn(fragment, out)


class CheckAcceptsTheExample(TreeCase):
    def test_pristine_example_has_no_errors_or_warnings(self):
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("0 errors, 0 warnings", out)


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
        self.replace(TRANSACTION, COMMAND_LINK, "./nope.code.skel.md#class-command")
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
        os.rename(self.path(TRANSACTION), self.path("skel/undo/transaction.skel.md"))
        self.assertCheckFails("stand-in name must be")

    def test_link_fragment_matching_no_heading_in_another_file(self):
        self.replace(TRANSACTION, COMMAND_LINK, "./command.code.skel.md#class-nosuch")
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
        self.replace(TRANSACTION, "[UndoHistory.begin_group](./history.code.skel.md#function-begin_group)",
                     "[Transaction.begin_group](./history.code.skel.md#function-begin_group)")
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
        _, listed = self.run_script(CHECK, "unknowns", "skel")
        self.assertIn("8 unknowns", listed)
        self.assertIn("8 unknowns", checked)

    def test_link_to_missing_file_in_system_file(self):
        self.append(SYSTEM, "\nSee [gone](./undo/gone.code.skel.md).\n")
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("SYSTEM.md", out)
        self.assertIn("link target does not exist", out)

    def test_dangling_fragment_in_system_file(self):
        self.append(SYSTEM, "\nSee [UndoHistory.nosuch](./undo/history.code.skel.md#function-nosuch).\n")
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("SYSTEM.md", out)
        self.assertIn("fragment '#function-nosuch' does not match any heading", out)

    def test_links_inside_fences_in_system_file_are_ignored(self):
        self.append(SYSTEM, "\n```text\n[gone](./undo/gone.code.skel.md)\n```\n")
        code, out = self.check()
        self.assertEqual(code, 0, out)


class UnknownsCommand(TreeCase):
    """TRANSACTION and COMMAND both say `Unknowns: none`; tests swap that line for a marker."""

    def unknowns(self, *args):
        return self.run_script(CHECK, "unknowns", "skel", *args)

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
        self.assertTrue(any(l.startswith("- [retry] undo/transaction.code.skel.md:") and
                            l.endswith("(module: transaction): How many retries. Kind: local. "
                                       "Proposed: three. Consequence: c. Unlocks: u.") for l in body), body)

    def test_blocking_unknown_is_listed_under_blocking(self):
        self.declare(COMMAND, "Which wire format. Kind: blocking. Consequence: c. Unlocks: u.")
        _, out = self.unknowns()
        body = self.group(out, "Blocking")
        self.assertTrue(any("undo/command.code.skel.md:" in l and "Which wire format." in l for l in body), body)

    def test_unknown_without_kind_is_listed_under_no_kind_stated(self):
        self.declare(COMMAND, "Something open. Consequence: c. Unlocks: u.")
        _, out = self.unknowns()
        body = self.group(out, "No kind stated")
        self.assertTrue(any("Something open." in l for l in body), body)

    def test_follower_is_listed_under_its_decision(self):
        self.declare(TRANSACTION, "[retry] How many retries. Kind: local. Proposed: three. Consequence: c. Unlocks: u.")
        self.declare(COMMAND, "Follows [retry]. Consequence: the retry loop here is unspecified.")
        _, out = self.unknowns()
        body = self.group(out, "Local")
        index = next(i for i, l in enumerate(body) if l.startswith("- [retry] "))
        follower = body[index + 1]
        self.assertTrue(follower.startswith("    followed at undo/command.code.skel.md:"), follower)
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
        self.assertTrue(any("undo/command.code.skel.md:" in l and "Follows [nosuch]" in l for l in body), body)

    def test_unknown_starting_with_a_link_is_not_named_after_it(self):
        self.declare(TRANSACTION, "[command](./command.code.skel.md) may gain a method. "
                                  "Kind: blocking. Consequence: c. Unlocks: u.")
        _, out = self.unknowns("--json")
        item = next(i for i in json.loads(out) if "may gain a method" in i["text"])
        self.assertIsNone(item["name"])

    def test_double_star_marker_parses_the_same(self):
        self.declare(TRANSACTION, "[retry] How many retries. Kind: local. Proposed: three. Consequence: c. Unlocks: u.",
                     marker="**UNKNOWN**")
        _, out = self.unknowns("--json")
        item = next(i for i in json.loads(out) if i.get("name") == "retry")
        self.assertEqual(item["kind"], "local")

    def test_json_carries_the_parsed_fields(self):
        self.declare(TRANSACTION, "[retry] How many retries. Kind: local. Proposed: three. Consequence: c. Unlocks: u.")
        self.declare(COMMAND, "Follows [retry]. Consequence: unspecified here.")
        _, out = self.unknowns("--json")
        item = next(i for i in json.loads(out) if i.get("name") == "retry")
        self.assertEqual(item["file"], "undo/transaction.code.skel.md")
        self.assertEqual(item["where"], "module: transaction")
        self.assertEqual(item["kind"], "local")
        self.assertEqual(item["proposed"], "three.")
        self.assertEqual(item["consequence"], "c.")
        self.assertEqual(item["unlocks"], "u.")
        self.assertEqual(len(item["followers"]), 1)
        follower = item["followers"][0]
        self.assertEqual(follower["file"], "undo/command.code.skel.md")
        self.assertEqual(follower["where"], "module: command")
        self.assertEqual(follower["consequence"], "unspecified here.")
        self.assertIsInstance(follower["line"], int)

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


class FixBacklinks(TreeCase):
    def test_write_restores_a_deleted_backlink(self):
        self.replace(COMMAND, BACKLINK, "")
        self.assertEqual(self.check()[0], 1)
        self.run_script(CHECK, "fix-backlinks", "skel", "--write")
        code, out = self.check()
        self.assertEqual(code, 0, out)

    def test_dry_run_changes_nothing(self):
        self.replace(COMMAND, BACKLINK, "")
        _, out = self.run_script(CHECK, "fix-backlinks", "skel")
        self.assertIn("dry run", out)
        self.assertEqual(self.check()[0], 1)


class Order(TreeCase):
    def test_cycle_is_flagged(self):
        self.replace(COMMAND, "- **Depends on:** [DocumentTarget](./document_target.code.skel.md#class-documenttarget)\n",
                     "- **Depends on:** [DocumentTarget](./document_target.code.skel.md#class-documenttarget)\n"
                     "- **Depends on:** [Transaction](./transaction.code.skel.md#class-transaction)\n")
        self.run_script(CHECK, "fix-backlinks", "skel", "--write")
        code, out = self.run_script(CHECK, "order", "skel")
        self.assertEqual(code, 0, out)
        self.assertIn("cycle", out)

    def test_dependencies_come_first(self):
        _, out = self.run_script(CHECK, "order", "skel")
        self.assertLess(out.index("undo/command.code"), out.index("undo/transaction.code"))


class Move(TreeCase):
    def test_moving_a_file_keeps_the_tree_valid(self):
        code, out = self.run_script(MV, "skel", COMMAND, "skel/src/undo/command.ts.skel.md")
        self.assertEqual(code, 0, out)
        self.assertTrue(os.path.exists(self.path("skel/src/undo/command.ts.skel.md")))
        code, out = self.check()
        self.assertEqual(code, 0, out)

    def test_moving_a_directory_keeps_the_tree_valid(self):
        code, out = self.run_script(MV, "skel", "skel/undo", "skel/src/core/undo")
        self.assertEqual(code, 0, out)
        code, out = self.check()
        self.assertEqual(code, 0, out)

    def test_dry_run_moves_nothing(self):
        self.run_script(MV, "skel", COMMAND, "skel/src/undo/command.ts.skel.md", "--dry-run")
        self.assertTrue(os.path.exists(self.path(COMMAND)))


class Status(TreeCase):
    def setUp(self):
        super().setUp()
        self.run_script(MV, "skel", COMMAND, "skel/src/command.py.skel.md")
        self.run_script(MV, "skel", TRANSACTION, "skel/src/transaction.py.skel.md")
        os.makedirs(self.path("src"))
        for name in ("command.py", "orphan.py"):
            with open(self.path(f"src/{name}"), "w", encoding="utf-8") as fh:
                fh.write("# placeholder\n")
        _, self.out = self.run_script(CHECK, "status", "skel", "--root", ".")

    def section(self, title):
        lines = self.out.splitlines()
        start = next(i for i, l in enumerate(lines) if l.startswith(title))
        body = []
        for line in lines[start + 1:]:
            if not line.startswith("  "):
                break
            body.append(line.strip())
        return lines[start], body

    def test_existing_file_is_implemented(self):
        head, body = self.section("Implemented")
        self.assertEqual(head, "Implemented (1):")
        self.assertEqual(body, ["src/command.py"])

    def test_missing_concrete_file_is_pending(self):
        head, body = self.section("Pending")
        self.assertEqual(head, "Pending (1):")
        self.assertEqual(body, ["src/transaction.py"])

    def test_abstract_stand_ins_are_listed_apart_from_pending(self):
        head, body = self.section("Abstract")
        self.assertEqual(head, "Abstract, adapt before implementing (5):")
        self.assertIn("infra/history_store.iac  [1 UNKNOWN]", body)

    def test_code_with_no_stand_in_is_reported(self):
        head, body = self.section("Code/IaC files with no stand-in")
        self.assertEqual(body, ["src/orphan.py"])


if __name__ == "__main__":
    unittest.main()
