import json
import re
import unittest

from support import MISC, NO_UNKNOWNS, PREMISE, STORY, TreeCase

DECL = "[venue] Which venue. Kind: blocking. Consequence: c. Unlocks: u."


class UnknownsCommand(TreeCase):
    def unknowns(self, *args):
        return self.run_wrist("unknowns", "wrist", *args)

    def declare(self, rel, text):
        self.replace(rel, NO_UNKNOWNS, f"*UNKNOWN*: {text}\n")

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

    def test_pristine_example_has_none(self):
        _, out = self.unknowns()
        self.assertIn("No unknowns.", out)

    def test_local_unknown_is_listed_under_local(self):
        self.declare(MISC, "[clocks] How many clocks. Kind: local. Proposed: eleven. Consequence: c. Unlocks: u.")
        _, out = self.unknowns()
        body = self.group(out, "Local")
        self.assertTrue(any(l.startswith("- [clocks] misc.md.wrist.md:") and "(misc: The Lamp)" in l
                            for l in body), body)

    def test_blocking_unknown_is_listed_under_blocking(self):
        self.declare(MISC, DECL)
        _, out = self.unknowns()
        body = self.group(out, "Blocking")
        self.assertTrue(any("misc.md.wrist.md:" in l and "Which venue." in l for l in body), body)

    def test_unknown_without_kind_is_listed_under_no_valid_kind(self):
        self.declare(MISC, "Something open. Consequence: c. Unlocks: u.")
        _, out = self.unknowns()
        self.assertTrue(any("Something open." in l for l in self.group(out, "No valid kind")))

    def test_follower_is_listed_beneath_its_declaration(self):
        self.declare(MISC, DECL)
        self.declare(STORY, "Follows [venue]. Consequence: the register of the dialogue.")
        _, out = self.unknowns()
        self.assertIn("    followed at work/the-lamp.md.wrist.md:", out)
        self.assertEqual(self.count(out), 1)

    def test_premise_unknown_is_labelled_premise(self):
        self.append(PREMISE, "\n*UNKNOWN*: [pen-name] Which name. Kind: blocking. Consequence: c. Unlocks: u.\n")
        _, out = self.unknowns()
        self.assertTrue(any(l.startswith("- [pen-name] PREMISE.md:") and "(premise)" in l
                            for l in self.group(out, "Blocking")))

    def test_check_and_unknowns_report_the_same_count(self):
        self.declare(MISC, DECL)
        _, checked = self.check()
        _, listed = self.unknowns()
        self.assertEqual(self.count(checked), 1)
        self.assertEqual(self.count(listed), 1)

    def test_json_items_share_one_shape(self):
        self.declare(MISC, "Follows [nosuch]. Consequence: unspecified here.")
        _, out = self.unknowns("--json")
        keys = {"file", "line", "where", "text", "name", "follows", "kind", "proposed", "consequence",
                "unlocks", "followers"}
        items = json.loads(out)
        self.assertTrue(items)
        for item in items:
            self.assertEqual(set(item), keys, item)


class UnknownRules(TreeCase):
    def declare(self, text, rel=MISC):
        self.replace(rel, NO_UNKNOWNS, f"*UNKNOWN*: {text}\n")

    def test_declaration_without_kind_is_an_error(self):
        self.declare("[venue] Which venue. Consequence: c. Unlocks: u.")
        self.assertCheckFails("*UNKNOWN* is missing `Kind:` (blocking or local)")

    def test_declaration_without_kind_is_a_warning_when_lenient(self):
        self.declare("[venue] Which venue. Consequence: c. Unlocks: u.")
        code, out = self.check("--lenient")
        self.assertEqual(code, 0, out)
        self.assertIn("warning: *UNKNOWN* is missing `Kind:`", out)

    def test_kind_must_be_blocking_or_local(self):
        self.declare("[venue] Which venue. Kind: maybe. Consequence: c. Unlocks: u.")
        self.assertCheckFails("*UNKNOWN* has `Kind: maybe`; it must be blocking or local")

    def test_local_unknown_needs_a_proposal(self):
        self.declare("[venue] Which venue. Kind: local. Consequence: c. Unlocks: u.")
        self.assertCheckFails("*UNKNOWN* with `Kind: local` needs `Proposed:`")

    def test_follower_of_an_undeclared_name_is_an_error(self):
        self.declare("Follows [nosuch]. Consequence: c.")
        self.assertCheckFails("`Follows [nosuch]` matches no declared unknown")

    def test_duplicate_name_is_an_error(self):
        self.declare(DECL)
        self.append(PREMISE, "\n*UNKNOWN*: [venue] Again. Kind: blocking. Consequence: c. Unlocks: u.\n")
        self.assertCheckFails("unknown name [venue] is already declared at")

    def test_name_must_be_lower_case(self):
        self.declare("[Venue] Which venue. Kind: blocking. Consequence: c. Unlocks: u.")
        self.assertCheckFails("must be lower-case letters, digits and hyphens")

    def test_premise_unknown_without_kind_is_an_error(self):
        self.append(PREMISE, "\n*UNKNOWN*: [pen-name] Which name. Consequence: c. Unlocks: u.\n")
        self.assertCheckFails("*UNKNOWN* is missing `Kind:`")

    def test_follower_with_extra_clauses_is_a_warning(self):
        self.declare(DECL)
        self.replace(STORY, NO_UNKNOWNS,
                     "*UNKNOWN*: Follows [venue]. Kind: blocking. Consequence: c.\n")
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("takes only `Consequence:`", out)

    def test_kind_inside_prose_is_not_a_clause(self):
        self.declare("[venue] Which venue, as in kind: magazine or anthology. Kind: blocking. "
                     "Consequence: c. Unlocks: u.")
        code, out = self.check()
        self.assertEqual(code, 0, out)

    def test_unknown_without_consequence_or_unlocks_is_a_warning(self):
        self.declare("[venue] Which venue. Kind: blocking.")
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("should state `Consequence:` and `Unlocks:`", out)


if __name__ == "__main__":
    unittest.main()
