import json
import os
import unittest

from support import OUTLINE, STORY, SYNOPSIS, TreeCase

SYNOPSIS_REAL = "synopsis.md"
STORY_REAL = "work/the-lamp.md"


class ExampleIsStamped(TreeCase):
    def test_example_is_fully_realized(self):
        code, out = self.run_wrist("status", "wrist")
        self.assertEqual(code, 0, out)
        self.assertIn("Realized (5):", out)
        for title in ("Stale", "Edited", "Unstamped", "Pending"):
            self.assertIn(f"{title}", out)
        self.assertNotIn("Pending (1)", out)


class Status(TreeCase):
    def groups(self):
        _, out = self.run_wrist("status", "wrist")
        groups, current = {}, None
        for line in out.splitlines():
            if line and not line.startswith(" "):
                current = line.split(" (")[0].split(",")[0]
                groups[current] = []
            elif line.strip():
                groups[current].append(line.strip().split("  ")[0])
        return groups

    def test_editing_a_realized_file_marks_it_edited(self):
        self.append(STORY_REAL, "\nA stray line.\n")
        self.assertEqual(self.groups()["Edited"], [STORY_REAL])

    def test_editing_a_stand_in_marks_its_file_stale(self):
        self.replace(SYNOPSIS, "She returns the lamp lit", "She returns the lamp, lit")
        self.assertEqual(self.groups()["Stale"], [SYNOPSIS_REAL])

    def test_a_backlink_change_does_not_make_a_file_stale(self):
        self.append(SYNOPSIS, "- **Referred by:** [story](./work/the-lamp.md.wrist.md)\n")
        self.assertEqual(self.groups()["Stale"], [])

    def test_missing_realized_file_is_pending(self):
        os.remove(self.path(STORY_REAL))
        self.assertEqual(self.groups()["Pending"], [STORY_REAL])

    def test_no_stamps_file_makes_everything_unstamped(self):
        os.remove(self.path("wrist/.stamps"))
        self.assertEqual(len(self.groups()["Unstamped"]), 5)

    def test_corrupt_stamps_file_is_reported(self):
        self.write("wrist/.stamps", "{not json")
        code, out = self.run_wrist("status", "wrist")
        self.assertNotEqual(code, 0)
        self.assertIn("cannot read the stamps", out)


class Stamp(TreeCase):
    def test_stamp_makes_an_edited_file_current_again(self):
        self.append(STORY_REAL, "\nA stray line.\n")
        code, out = self.run_wrist("stamp", "wrist", STORY_REAL)
        self.assertEqual(code, 0, out)
        self.assertIn("stamped work/the-lamp.md", out)
        _, status = self.run_wrist("status", "wrist")
        self.assertIn("Realized (5):", status)

    def test_stamp_all_covers_every_realized_file(self):
        os.remove(self.path("wrist/.stamps"))
        code, out = self.run_wrist("stamp", "wrist", "--all")
        self.assertEqual(code, 0, out)
        self.assertIn("5 stamped", out)
        with open(self.path("wrist/.stamps"), encoding="utf-8") as fh:
            stamps = json.load(fh)
        self.assertEqual(set(stamps["work/the-lamp.md"]), {"stand_in", "realized", "date"})

    def test_stamping_a_file_not_yet_realized_fails(self):
        os.remove(self.path(STORY_REAL))
        code, out = self.run_wrist("stamp", "wrist", STORY_REAL)
        self.assertEqual(code, 1, out)
        self.assertIn("not realized yet", out)

    def test_stamping_a_path_with_no_stand_in_fails(self):
        self.write("notes.md", "x\n")
        code, out = self.run_wrist("stamp", "wrist", "notes.md")
        self.assertEqual(code, 1, out)
        self.assertIn("no stand-in in this tree", out)

    def test_stamp_needs_paths_or_all(self):
        code, out = self.run_wrist("stamp", "wrist")
        self.assertNotEqual(code, 0)
        self.assertIn("--all", out)

    def test_realized_files_are_never_modified_by_stamping(self):
        before = self.read(STORY_REAL)
        self.run_wrist("stamp", "wrist", "--all")
        self.assertEqual(self.read(STORY_REAL), before)


class Order(TreeCase):
    def test_order_follows_the_profile(self):
        code, out = self.run_wrist("order", "wrist")
        self.assertEqual(code, 0, out)
        names = [l.split()[1] for l in out.splitlines() if l[:1].isdigit()]
        self.assertEqual(names, ["synopsis.md", "outline.md", "character.md", "misc.md", "work/the-lamp.md"])
        self.assertNotIn("contradict", out)
        self.assertIn("1. synopsis.md  (synopsis)", out)
        self.assertIn("5. work/the-lamp.md  (story)", out)

    def test_a_dependency_on_a_later_file_is_reported_but_is_not_an_error(self):
        self.append(SYNOPSIS, "- **Depends on:** [story](./work/the-lamp.md.wrist.md) (mentions)\n")
        self.run_wrist("fix-backlinks", "wrist", "--write")
        code, out = self.run_wrist("order", "wrist")
        self.assertEqual(code, 0, out)
        self.assertIn("synopsis.md depends on work/the-lamp.md, which is realized later", out)

    def test_json_output(self):
        _, out = self.run_wrist("order", "wrist", "--json")
        data = json.loads(out)
        self.assertEqual(data["order"][0]["realizes"], "synopsis.md")
        self.assertEqual(data["conflicts"], [])


class DamagedStamps(TreeCase):
    def test_stamp_repairs_an_entry_that_is_not_an_object(self):
        self.write("wrist/.stamps", json.dumps({"work/the-lamp.md": "abc", "outline.md": ["x"]}))
        code, out = self.run_wrist("stamp", "wrist", "--all")
        self.assertEqual(code, 0, out)
        self.assertNotIn("Traceback", out)
        _, status = self.run_wrist("status", "wrist")
        self.assertIn("Realized (5):", status)

    def test_an_unreadable_realized_file_is_reported_not_a_traceback(self):
        os.remove(self.path(STORY_REAL))
        os.mkdir(self.path(STORY_REAL))
        code, out = self.run_wrist("status", "wrist")
        self.assertNotIn("Traceback", out)


if __name__ == "__main__":
    unittest.main()
