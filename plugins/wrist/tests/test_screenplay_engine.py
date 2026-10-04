import json
import os
import shutil
import tempfile
import unittest

from support import TreeCase     # first: it puts the scripts folder on sys.path

import wrist_profile as wp


def base(**extra):
    data = {"name": "tiny", "files": [{"path": "a.md", "function": "a", "order": 1}],
            "functions": {"a": {"heading": "a", "prose": True}}, "relations": [], "limits": {"max_prose_words": 50}}
    data.update(extra)
    return data


class Settings(unittest.TestCase):
    def test_defaults(self):
        p = wp.parse_profile(base())
        self.assertIsNone(p.publish_style)
        self.assertEqual(p.lint_format, "prose")

    def test_a_publish_style_is_read(self):
        self.assertEqual(wp.parse_profile(base(publish={"style": "screenplay"})).publish_style, "screenplay")

    def test_publish_must_be_an_object_with_only_a_style_name(self):
        for bad in ("screenplay", {}, {"style": 3}, {"style": "Bad Name"}, {"style": "ok", "colour": 1}):
            with self.subTest(bad=bad):
                with self.assertRaises(wp.ProfileError) as cm:
                    wp.parse_profile(base(publish=bad))
                self.assertIn("'publish'", str(cm.exception))

    def test_lint_format_must_be_known(self):
        self.assertEqual(wp.parse_profile(base(lint_format="fountain")).lint_format, "fountain")
        with self.assertRaises(wp.ProfileError) as cm:
            wp.parse_profile(base(lint_format="markdown"))
        self.assertIn("'lint_format' must be one of prose, fountain", str(cm.exception))


class ScopesFollowTheFormat(unittest.TestCase):
    GOOD = {"id": "x", "pattern": "a", "label": "l", "note": "n", "scope": "anywhere", "positive": "a", "negative": "b"}

    def load(self, lint_format, scope):
        d = tempfile.mkdtemp(prefix="wrist-scope-")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        os.makedirs(os.path.join(d, "t"))
        with open(os.path.join(d, "t", "profile.json"), "w") as fh:
            json.dump(base(lint_format=lint_format), fh)
        with open(os.path.join(d, "t", "lint.json"), "w") as fh:
            json.dump({"items": [dict(self.GOOD, scope=scope)]}, fh)
        return wp.load_profile("t", d).lint_items()

    def test_fountain_scopes_are_accepted_for_a_fountain_profile(self):
        for scope in ("action", "dialogue", "anywhere"):
            self.assertEqual(len(self.load("fountain", scope)), 1)

    def test_prose_scopes_are_rejected_for_a_fountain_profile(self):
        with self.assertRaises(wp.ProfileError) as cm:
            self.load("fountain", "narration")
        self.assertIn("scope must be one of action, dialogue, anywhere", str(cm.exception))

    def test_fountain_scopes_are_rejected_for_a_prose_profile(self):
        with self.assertRaises(wp.ProfileError) as cm:
            self.load("prose", "action")
        self.assertIn("scope must be one of narration, anywhere", str(cm.exception))

    def test_the_existing_profiles_still_load(self):
        self.assertEqual(wp.load_profile("shortstory").lint_format, "prose")
        self.assertEqual(wp.load_profile("novel").lint_format, "prose")
        self.assertGreater(len(wp.load_profile("novel").lint_items()), 20)


class UnderscoredKeys(unittest.TestCase):
    def test_a_premise_key_may_contain_underscores(self):
        data = base(premise_keys={"act_headings": {"type": "bool"}},
                    files=[{"path": "a.md", "function": "a", "order": 1, "when": "act_headings"}])
        p = wp.parse_profile(data)
        p.set_premise({"act_headings": "yes"})
        self.assertEqual([path for path, _ in p.expected_files("s")], ["a.md"])

    def test_a_question_id_matches_a_premise_key_with_hyphens_or_underscores(self):
        data = base(premise_keys={"act_headings": {"type": "bool"}})
        p = wp.parse_profile(data, "- [deferrable] act-headings: Should acts be labelled?\n")
        self.assertEqual([q.id for q in p.questions], ["act-headings"])
        self.assertEqual(p.question_key("act-headings"), "act_headings")
        self.assertIsNone(p.question_key("genre"))


if __name__ == "__main__":
    unittest.main()
