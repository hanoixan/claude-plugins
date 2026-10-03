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


if __name__ == "__main__":
    unittest.main()
