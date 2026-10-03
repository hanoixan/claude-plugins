import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from support import CHECK

import wrist_profile as wp


def mini():
    return {
        "name": "mini",
        "files": [
            {"path": "intro.md", "function": "intro", "order": 1},
            {"path": "work/prologue.md", "function": "part", "order": 2, "when": "prologue"},
            {"path": "work/chapter-{n}.md", "function": "chapter", "order": 3, "family": "chapters"},
        ],
        "premise_keys": {
            "chapters": {"type": "int", "min": 1, "max": 200, "required": True},
            "prologue": {"type": "bool"},
        },
        "functions": {
            "intro": {"heading": "intro"},
            "part": {"heading": "part", "fields": ["Heading"], "heading_field": "Heading", "prose": True},
            "chapter": {"heading": "chapter", "fields": ["Heading"], "heading_field": "Heading",
                        "required_when_realized": ["Noted"], "sequence": True, "prose": True},
        },
        "relations": ["continues", "mentions"],
        "limits": {"max_prose_words": 120},
    }


def bound(**front):
    p = wp.parse_profile(mini())
    p.set_premise({k: str(v) for k, v in front.items()})
    return p


class ProfileEngine(unittest.TestCase):
    def paths(self, p, slug="mini"):
        return [path for path, _ in p.expected_files(slug)]

    def test_a_family_expands_to_one_file_per_number(self):
        self.assertEqual(self.paths(bound(chapters=3)),
                         ["intro.md", "work/chapter-1.md", "work/chapter-2.md", "work/chapter-3.md"])

    def test_numbers_are_zero_padded_to_the_width_of_the_count(self):
        self.assertIn("work/chapter-09.md", self.paths(bound(chapters=10)))
        self.assertNotIn("work/chapter-9.md", self.paths(bound(chapters=10)))
        self.assertIn("work/chapter-001.md", self.paths(bound(chapters=100)))
        self.assertIn("work/chapter-9.md", self.paths(bound(chapters=9)))

    def test_a_when_file_exists_only_when_its_key_is_true(self):
        self.assertNotIn("work/prologue.md", self.paths(bound(chapters=1)))
        self.assertNotIn("work/prologue.md", self.paths(bound(chapters=1, prologue="no")))
        for word in ("yes", "YES", "true", "True"):
            self.assertIn("work/prologue.md", self.paths(bound(chapters=1, prologue=word)))

    def test_order_follows_the_profile_then_the_number(self):
        self.assertEqual(self.paths(bound(chapters=2, prologue="yes")),
                         ["intro.md", "work/prologue.md", "work/chapter-1.md", "work/chapter-2.md"])

    def test_function_for_uses_the_bound_premise(self):
        p = bound(chapters=3)
        self.assertEqual(p.function_for("work/chapter-2.md", "mini"), "chapter")
        self.assertIsNone(p.function_for("work/chapter-4.md", "mini"))
        self.assertIsNone(p.function_for("work/prologue.md", "mini"))

    def test_explicit_options_override_the_bound_ones(self):
        p = bound(chapters=3)
        self.assertEqual(len(p.expected_files("mini", {"chapters": 5, "prologue": False})), 6)

    def test_sequence_prev_links_each_chapter_to_the_one_before(self):
        prev = bound(chapters=3).sequence_prev("mini")
        self.assertEqual(prev, {"work/chapter-2.md": "work/chapter-1.md", "work/chapter-3.md": "work/chapter-2.md"})

    def test_labels_include_fields_that_are_only_required_once_realized(self):
        self.assertIn("Noted", bound(chapters=1).labels())

    def test_an_unbound_profile_has_no_family_files(self):
        p = wp.parse_profile(mini())
        self.assertEqual([path for path, _ in p.expected_files("mini")], ["intro.md"])


class OptionProblems(unittest.TestCase):
    def problems(self, **front):
        p = bound(**front)
        return dict(p.option_problems)

    def test_a_valid_premise_has_no_problems(self):
        self.assertEqual(self.problems(chapters=3, prologue="yes"), {})

    def test_a_missing_required_key(self):
        self.assertEqual(self.problems(), {"chapters": "`chapters:` is required (a whole number from 1 to 200)"})

    def test_a_blank_value_counts_as_missing(self):
        self.assertIn("is required", self.problems(chapters="  ")["chapters"])

    def test_text_is_not_a_number(self):
        self.assertEqual(self.problems(chapters="ten")["chapters"],
                         "`chapters:` must be a whole number from 1 to 200 (got 'ten')")

    def test_out_of_range_numbers(self):
        for value in ("0", "201", "-3", "3.5", "1e2"):
            with self.subTest(value=value):
                self.assertIn("must be a whole number from 1 to 200", self.problems(chapters=value)["chapters"])

    def test_bounds_are_inclusive(self):
        self.assertEqual(self.problems(chapters=1), {})
        self.assertEqual(self.problems(chapters=200), {})

    def test_a_bad_bool(self):
        self.assertEqual(self.problems(chapters=1, prologue="maybe")["prologue"],
                         "`prologue:` must be yes or no (got 'maybe')")

    def test_a_bad_value_leaves_the_file_set_empty_not_broken(self):
        p = bound(chapters="ten", prologue="maybe")
        self.assertEqual([path for path, _ in p.expected_files("mini")], ["intro.md"])

    def test_the_range_reads_at_least_without_a_maximum(self):
        data = mini()
        del data["premise_keys"]["chapters"]["max"]
        p = wp.parse_profile(data)
        p.set_premise({"chapters": "x"})
        self.assertEqual(dict(p.option_problems)["chapters"], "`chapters:` must be a whole number at least 1 (got 'x')")


class SchemaRules(unittest.TestCase):
    def rejected(self, mutate, fragment):
        data = mini()
        mutate(data)
        with self.assertRaises(wp.ProfileError) as cm:
            wp.parse_profile(data)
        self.assertIn(fragment, str(cm.exception))

    def test_when_must_name_a_bool_key(self):
        self.rejected(lambda d: d["files"][1].update(when="chapters"), "'when' must name a bool premise key")
        self.rejected(lambda d: d["files"][1].update(when="nosuch"), "'when' must name a bool premise key")

    def test_family_must_name_an_int_key(self):
        self.rejected(lambda d: d["files"][2].update(family="prologue"), "'family' must name an int premise key")

    def test_a_file_cannot_be_both_when_and_family(self):
        self.rejected(lambda d: d["files"][2].update(when="prologue"), "cannot have both 'when' and 'family'")

    def test_only_a_family_path_may_contain_n(self):
        self.rejected(lambda d: d["files"][2].update(path="work/chapter.md"), "must contain {n}")
        self.rejected(lambda d: d["files"][1].update(path="work/{n}.md"), "must contain {n}")

    def test_unknown_file_key(self):
        self.rejected(lambda d: d["files"][0].update(colour="red"), "unknown key 'colour'")

    def test_premise_key_type(self):
        self.rejected(lambda d: d["premise_keys"]["prologue"].update(type="text"), "'type' must be one of bool, int")

    def test_bounds_only_for_int_keys(self):
        self.rejected(lambda d: d["premise_keys"]["prologue"].update(min=1), "'min' is only for int keys")

    def test_premise_key_unknown_setting(self):
        self.rejected(lambda d: d["premise_keys"]["prologue"].update(colour=1), "unknown key 'colour'")

    def test_heading_field_must_be_one_of_the_fields(self):
        self.rejected(lambda d: d["functions"]["part"].update(heading_field="Nope"),
                      "'heading_field' must be one of its fields")

    def test_a_realized_only_field_cannot_also_be_always_required(self):
        self.rejected(lambda d: d["functions"]["chapter"].update(required_when_realized=["Heading"]),
                      "cannot be both always required and required_when_realized")

    def test_sequence_must_be_a_bool(self):
        self.rejected(lambda d: d["functions"]["chapter"].update(sequence="yes"), "'sequence' must be true or false")

    def test_a_profile_without_premise_keys_still_loads(self):
        data = mini()
        del data["premise_keys"]
        data["files"] = [data["files"][0]]
        self.assertEqual(wp.parse_profile(data).premise_keys, {})

    def test_the_shortstory_profile_is_unchanged(self):
        p = wp.load_profile("shortstory")
        self.assertEqual(p.premise_keys, {})
        self.assertEqual(len(p.expected_files("the-lamp")), 5)


class CheckEngine(unittest.TestCase):
    """The checker run on a project built from the two-key `mini` profile."""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="wrist-fam-")
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        prof = os.path.join(self.dir, "profiles", "mini")
        os.makedirs(prof)
        with open(os.path.join(prof, "profile.json"), "w") as fh:
            json.dump(mini(), fh)
        self.project = os.path.join(self.dir, "project")
        self.env = dict(os.environ, WRIST_PROFILES_DIR=os.path.join(self.dir, "profiles"))
        self.build(3)

    def put(self, rel, text):
        path = os.path.join(self.project, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def read(self, rel):
        with open(os.path.join(self.project, rel), encoding="utf-8") as fh:
            return fh.read()

    def premise(self, chapters=3, prologue=None, extra=""):
        front = ["profile: mini", "title: Mini", "slug: mini", f"chapters: {chapters}"]
        if prologue is not None:
            front.append(f"prologue: {prologue}")
        front += ["questions_generation: done", "questions_realization: done", "questions_publishing: done",
                  "review_done: yes", "author: A. Writer"]
        self.put("wrist/PREMISE.md", "---\n" + "\n".join(front) + extra + "\n---\n\n# Premise\n")

    def chapter_names(self, n):
        width = len(str(n))
        return [str(i).zfill(width) for i in range(1, n + 1)]

    def build(self, n, noted=False, realize=False):
        """A clean project: intro plus n chapters chained with (continues)."""
        shutil.rmtree(self.project, ignore_errors=True)
        self.premise(n)
        self.put("wrist/intro.md.wrist.md",
                 "# intro: Mini\n\n- **Required:** always\n- **Rules:** none\n- **Depends on:** none\n"
                 "- **Referred by:** none\n- **Unknowns:** none\n")
        names = self.chapter_names(n)
        for i, name in enumerate(names):
            lines = [f"# chapter: Chapter {name}", "", f"- **Heading:** `# {i + 1}. Title`",
                     "- **Required:** always", "- **Rules:** none"]
            lines.append(f"- **Depends on:** [Chapter {names[i - 1]}](./chapter-{names[i - 1]}.md.wrist.md) (continues)"
                         if i else "- **Depends on:** none")
            lines.append(f"- **Referred by:** [Chapter {names[i + 1]}](./chapter-{names[i + 1]}.md.wrist.md)"
                         if i + 1 < n else "- **Referred by:** none")
            lines.append("- **Unknowns:** none")
            if noted:
                lines.append("- **Noted:** something happened")
            self.put(f"wrist/work/chapter-{name}.md.wrist.md", "\n".join(lines) + "\n")
            if realize:
                self.put(f"work/chapter-{name}.md", f"# {i + 1}. Title\n\nWords here.\n")

    def run_cli(self, *args):
        proc = subprocess.run([sys.executable, CHECK, *args], cwd=self.project, env=self.env,
                              capture_output=True, text=True)
        return proc.returncode, proc.stdout + proc.stderr

    def check(self):
        return self.run_cli("check", "wrist")

    def test_a_clean_project_passes(self):
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("4 stand-ins", out)
        self.assertIn("0 errors, 0 warnings", out)

    def test_review_focus_raising_the_chapter_count_after_generation(self):
        self.premise(4)
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("required stand-in missing: wrist/work/chapter-4.md.wrist.md", out)

    def test_review_focus_lowering_the_chapter_count_after_generation(self):
        self.premise(2)
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("outside the mini shape", out)

    def test_review_focus_the_padding_width_changes_at_ten(self):
        self.build(10)
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertTrue(os.path.exists(os.path.join(self.project, "wrist/work/chapter-01.md.wrist.md")))
        self.premise(9)
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("required stand-in missing: wrist/work/chapter-1.md.wrist.md", out)
        self.assertIn("outside the mini shape", out)

    def test_review_focus_each_bad_premise_value_is_a_clear_error(self):
        cases = [("chapters: ten", "`chapters:` must be a whole number from 1 to 200 (got 'ten')"),
                 ("chapters: 0", "must be a whole number from 1 to 200 (got '0')"),
                 ("chapters: 201", "must be a whole number from 1 to 200 (got '201')"),
                 ("prologue: maybe", "`prologue:` must be yes or no (got 'maybe')")]
        for line, fragment in cases:
            with self.subTest(line=line):
                self.build(3)
                text = self.read("wrist/PREMISE.md")
                key = line.split(":")[0]
                if key in text:
                    text = "\n".join(l for l in text.split("\n") if not l.startswith(key + ":"))
                self.put("wrist/PREMISE.md", text.replace("---\n\n# Premise", line + "\n---\n\n# Premise", 1))
                code, out = self.check()
                self.assertEqual(code, 1, out)
                self.assertNotIn("Traceback", out)
                self.assertIn(fragment, out)

    def test_review_focus_a_missing_chapters_key(self):
        text = "\n".join(l for l in self.read("wrist/PREMISE.md").split("\n") if not l.startswith("chapters:"))
        self.put("wrist/PREMISE.md", text)
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("`chapters:` is required (a whole number from 1 to 200)", out)
        self.assertNotIn("Traceback", out)

    def test_a_when_file_must_exist_when_its_key_is_true_and_not_otherwise(self):
        self.premise(3, prologue="yes")
        code, out = self.check()
        self.assertIn("required stand-in missing: wrist/work/prologue.md.wrist.md", out)
        self.premise(3, prologue="no")
        self.put("wrist/work/prologue.md.wrist.md", "# part: P\n")
        code, out = self.check()
        self.assertIn("outside the mini shape", out)

    def test_a_chapter_without_a_continues_link_to_the_one_before_is_a_warning(self):
        path = "wrist/work/chapter-2.md.wrist.md"
        text = self.read(path).replace(" (continues)", " (mentions)")
        self.put(path, text)
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("no `Depends on:` link to work/chapter-1.md's stand-in with the relation `continues`", out)

    def test_the_first_chapter_needs_no_continues_link(self):
        code, out = self.check()
        self.assertNotIn("continues", out)

    # --- stamp, gate: required_when_realized and the heading field -------------------------------

    def stamp(self, *paths):
        return self.run_cli("stamp", "wrist", *paths)

    def test_stamp_refuses_a_realized_file_whose_stand_in_lacks_the_field(self):
        self.build(3, realize=True)
        code, out = self.stamp("work/chapter-1.md")
        self.assertEqual(code, 1, out)
        self.assertIn("work/chapter-1.md: its stand-in has no `Noted:` text; fill it in first", out)
        self.assertFalse(os.path.exists(os.path.join(self.project, "wrist/.stamps")))

    def test_stamp_accepts_the_field_on_one_line(self):
        self.build(3, noted=True, realize=True)
        code, out = self.stamp("work/chapter-1.md")
        self.assertEqual(code, 0, out)
        self.assertIn("stamped work/chapter-1.md", out)

    def test_review_focus_an_empty_field_does_not_count(self):
        self.build(3, realize=True)
        path = "wrist/work/chapter-1.md.wrist.md"
        self.put(path, self.read(path) + "- **Noted:**\n\n")
        code, out = self.stamp("work/chapter-1.md")
        self.assertEqual(code, 1, out)
        self.assertIn("no `Noted:` text", out)

    def test_review_focus_text_on_following_bullet_lines_counts(self):
        self.build(3, realize=True)
        path = "wrist/work/chapter-1.md.wrist.md"
        self.put(path, self.read(path) + "- **Noted:**\n  - first fact\n  - second fact\n")
        code, out = self.stamp("work/chapter-1.md")
        self.assertEqual(code, 0, out)

    def test_stamp_all_names_every_chapter_that_owes_the_field(self):
        self.build(3, realize=True)
        code, out = self.stamp("--all")
        self.assertEqual(code, 1, out)
        for n in (1, 2, 3):
            self.assertIn(f"work/chapter-{n}.md: its stand-in has no `Noted:` text", out)

    def ready(self):
        """Three realized, stamped chapters, ready for the publishing gate."""
        self.build(3, noted=True, realize=True)
        self.put("intro.md", "text\n")
        code, out = self.stamp("--all")
        self.assertEqual(code, 0, out)

    def gate(self, phase="publishing"):
        return self.run_cli("gate", "wrist", phase)

    def test_the_publishing_gate_is_open_when_everything_is_in_order(self):
        self.ready()
        code, out = self.gate()
        self.assertEqual(code, 0, out)

    def test_the_gate_blocks_when_a_realized_file_lost_its_field(self):
        self.ready()
        path = "wrist/work/chapter-2.md.wrist.md"
        self.put(path, self.read(path).replace("- **Noted:** something happened\n", ""))
        code, out = self.gate()
        self.assertEqual(code, 1, out)
        self.assertIn("work/chapter-2.md: its stand-in has no `Noted:` text; fill it in, then stamp", out)

    def test_review_focus_a_heading_that_does_not_match_blocks_publishing(self):
        self.ready()
        with open(os.path.join(self.project, "work/chapter-2.md"), "w", encoding="utf-8") as fh:
            fh.write("# 2 Title\n\nWords here.\n")
        self.stamp("work/chapter-2.md")
        code, out = self.gate()
        self.assertEqual(code, 1, out)
        self.assertIn("work/chapter-2.md starts with '# 2 Title' but its stand-in's `Heading:` says '# 2. Title'", out)

    def test_a_leading_blank_line_or_bom_does_not_hide_the_heading(self):
        self.ready()
        with open(os.path.join(self.project, "work/chapter-2.md"), "w", encoding="utf-8-sig") as fh:
            fh.write("\n\n# 2. Title\n\nWords here.\n")
        self.stamp("work/chapter-2.md")
        code, out = self.gate()
        self.assertEqual(code, 0, out)

    def test_order_status_and_lint_see_the_family(self):
        self.build(3, noted=True, realize=True)
        code, out = self.run_cli("order", "wrist")
        self.assertEqual([l.split()[1] for l in out.splitlines() if l[:1].isdigit()],
                         ["intro.md", "work/chapter-1.md", "work/chapter-2.md", "work/chapter-3.md"])
        code, out = self.run_cli("status", "wrist")
        self.assertIn("Pending (1):", out)       # intro.md has no realized file yet
        code, out = self.run_cli("lint", "wrist")
        self.assertEqual(code, 0, out)


if __name__ == "__main__":
    unittest.main()
