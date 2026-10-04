import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from support import SCRIPTS, SKILL

import wrist_profile as wp


def base():
    return {
        "name": "tiny",
        "files": [{"path": "a.md", "function": "alpha", "order": 1},
                  {"path": "work/{slug}.md", "function": "beta", "order": 2}],
        "functions": {"alpha": {"heading": "alpha", "fields": ["Hue"], "children": {"bead": ["Size"]}},
                      "beta": {"heading": "beta", "prose": True}},
        "relations": ["Uses"],
        "limits": {"max_prose_words": 50},
    }


class ShortstoryProfile(unittest.TestCase):
    def setUp(self):
        self.p = wp.load_profile("shortstory")

    def test_file_shape_follows_realization_order(self):
        self.assertEqual(self.p.expected_files("the-lamp"), [
            ("synopsis.md", "synopsis"), ("outline.md", "outline"), ("character.md", "characters"),
            ("misc.md", "misc"), ("work/the-lamp.md", "story")])

    def test_slug_files_are_skipped_without_a_slug(self):
        self.assertNotIn("story", [fn for _, fn in self.p.expected_files("")])

    def test_function_for_matches_a_mirrored_path(self):
        self.assertEqual(self.p.function_for("work/the-lamp.md", "the-lamp"), "story")
        self.assertIsNone(self.p.function_for("work/other.md", "the-lamp"))

    def test_labels_cover_every_declared_field(self):
        for label in ("Logline", "Wants", "Flaw", "Voice", "Facts", "Point of view", "Must include"):
            self.assertIn(label, self.p.labels())

    def test_questions_are_parsed_with_their_kind(self):
        ids = [q.id for q in self.p.questions]
        self.assertEqual(len(ids), len(set(ids)))
        required = {q.id for q in self.p.questions if q.required}
        self.assertEqual(required, {"genre", "audience", "length", "tone", "viewpoint", "premise", "ending"})
        self.assertEqual(len(self.p.questions), 13)

    def test_only_the_story_is_prose(self):
        self.assertEqual([n for n, s in self.p.functions.items() if s["prose"]], ["story"])

    def test_relations_are_lower_case(self):
        self.assertIn("appears", self.p.relations)

    def test_a_short_story_has_no_title_page(self):
        self.assertIs(self.p.title_page, False)


class Validation(unittest.TestCase):
    def assertRejected(self, data, fragment, questions=""):
        with self.assertRaises(wp.ProfileError) as cm:
            wp.parse_profile(data, questions)
        self.assertIn(fragment, str(cm.exception))

    def test_a_valid_profile_loads_and_defaults_are_filled(self):
        p = wp.parse_profile(base())
        self.assertEqual(p.functions["beta"]["children"], {})
        self.assertEqual(p.functions["beta"]["fields"], [])
        self.assertEqual(p.relations, ["uses"])

    def test_title_page_defaults_to_true(self):
        self.assertIs(wp.parse_profile(base()).title_page, True)

    def test_title_page_must_be_true_or_false(self):
        data = base()
        data["title_page"] = "yes"
        self.assertRejected(data, "'title_page' must be true or false")

    def test_missing_key(self):
        data = base()
        del data["limits"]
        self.assertRejected(data, "missing 'limits'")

    def test_unknown_top_level_key(self):
        data = base()
        data["colour"] = "red"
        self.assertRejected(data, "unknown key 'colour'")

    def test_file_uses_an_undeclared_function(self):
        data = base()
        data["files"][0]["function"] = "gamma"
        self.assertRejected(data, "undeclared function 'gamma'")

    def test_duplicate_path(self):
        data = base()
        data["files"][1]["path"] = "a.md"
        self.assertRejected(data, "'a.md' is listed twice")

    def test_order_must_be_an_integer(self):
        data = base()
        data["files"][0]["order"] = "first"
        self.assertRejected(data, "integer 'order'")

    def test_heading_names_are_restricted(self):
        data = base()
        data["functions"]["alpha"]["heading"] = "Not Valid"
        self.assertRejected(data, "heading")

    def test_unknown_function_key(self):
        data = base()
        data["functions"]["alpha"]["colour"] = 1
        self.assertRejected(data, "unknown key 'colour'")

    def test_limit_must_be_positive(self):
        data = base()
        data["limits"]["max_prose_words"] = 0
        self.assertRejected(data, "max_prose_words")

    def test_duplicate_question_id(self):
        self.assertRejected(base(), "asked twice",
                            "- [required] genre: One?\n- [deferrable] genre: Two?\n")


class Loading(unittest.TestCase):
    def test_unknown_profile_lists_what_exists(self):
        with self.assertRaises(wp.ProfileError) as cm:
            wp.load_profile("sonnet")
        self.assertIn("no profile 'sonnet'", str(cm.exception))
        self.assertIn("shortstory", str(cm.exception))

    def test_a_name_cannot_climb_out_of_the_profiles_folder(self):
        with self.assertRaises(wp.ProfileError):
            wp.load_profile("../scripts")

    def test_invalid_json_is_reported(self):
        d = tempfile.mkdtemp(prefix="wrist-prof-")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        os.makedirs(os.path.join(d, "bad"))
        with open(os.path.join(d, "bad", "profile.json"), "w") as fh:
            fh.write("{not json")
        with self.assertRaises(wp.ProfileError) as cm:
            wp.load_profile("bad", d)
        self.assertIn("not valid JSON", str(cm.exception))

    def test_environment_variable_selects_the_profiles_folder(self):
        d = tempfile.mkdtemp(prefix="wrist-prof-")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        os.makedirs(os.path.join(d, "tiny"))
        with open(os.path.join(d, "tiny", "profile.json"), "w") as fh:
            json.dump(base(), fh)
        code = ("import sys; sys.path.insert(0, %r); import wrist_profile as w; "
                "print(w.load_profile('tiny').name)" % SCRIPTS)
        env = dict(os.environ, WRIST_PROFILES_DIR=d)
        out = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True)
        self.assertEqual(out.stdout.strip(), "tiny", out.stderr)


class ReferenceContent(unittest.TestCase):
    def read(self, name):
        with open(os.path.join(SKILL, "profiles", "shortstory", name), encoding="utf-8") as fh:
            return fh.read()

    def test_structures_cover_the_planned_forms(self):
        text = self.read("structures.md")
        for name in ("Freytag", "three-act", "In medias res", "Kishōtenketsu", "Story spine", "Vignette"):
            self.assertIn(name, text)
        self.assertEqual(text.count("**Best for:**"), text.count("\n## "))

    def test_quality_has_the_three_parts(self):
        text = self.read("quality.md")
        for heading in ("## Clichés and stock moves", "## Marks of low quality", "## Judgment checklist"):
            self.assertIn(heading, text)
        self.assertGreaterEqual(text.count("- [ ] "), 10)


if __name__ == "__main__":
    unittest.main()
