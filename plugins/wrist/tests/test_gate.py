import os
import unittest

from support import MISC, NO_UNKNOWNS, PREMISE, STORY, SYNOPSIS, TreeCase

STORY_REAL = "work/the-lamp.md"


class Gates(TreeCase):
    def gate(self, phase):
        return self.run_wrist("gate", "wrist", phase)

    def assertBlocked(self, phase, fragment):
        code, out = self.gate(phase)
        self.assertEqual(code, 1, out)
        self.assertIn("blocked", out)
        self.assertIn(fragment, out)

    def test_every_gate_is_open_on_the_example(self):
        for phase in ("generation", "realization", "publishing"):
            code, out = self.gate(phase)
            self.assertEqual(code, 0, out)
            self.assertIn(f"gate {phase}: open", out)

    def test_each_phase_needs_its_question_phase(self):
        for phase in ("generation", "realization", "publishing"):
            with self.subTest(phase=phase):
                self.replace(PREMISE, f"questions_{phase}: done\n", "")
                self.assertBlocked(phase, f"the question phase before {phase}")
                self.replace(PREMISE, "---\n\n# Premise", f"questions_{phase}: done\n---\n\n# Premise")

    def test_generation_needs_the_required_answers(self):
        self.replace(PREMISE, "- **genre:** Literary fiction, quiet realism.\n", "")
        self.assertBlocked("generation", "question 'genre'")

    def test_realization_is_blocked_by_a_check_error(self):
        self.replace(SYNOPSIS, "- **Referred by:** [outline](./outline.md.wrist.md)\n", "")
        self.assertBlocked("realization", "`check` reports")

    def test_realization_is_blocked_by_a_blocking_unknown(self):
        self.replace(MISC, NO_UNKNOWNS, "*UNKNOWN*: [venue] Which venue. Kind: blocking. "
                                         "Consequence: c. Unlocks: u.\n")
        self.assertBlocked("realization", "blocking unknown at misc.md.wrist.md")

    def test_a_local_unknown_does_not_block_realization(self):
        self.replace(MISC, NO_UNKNOWNS, "*UNKNOWN*: [clocks] How many. Kind: local. Proposed: eleven. "
                                         "Consequence: c. Unlocks: u.\n")
        self.assertEqual(self.gate("realization")[0], 0)

    def test_publishing_is_blocked_by_a_hand_edited_realized_file(self):
        self.append(STORY_REAL, "\nA stray line.\n")
        self.assertBlocked("publishing", "work/the-lamp.md is edited")

    def test_publishing_is_blocked_by_a_changed_stand_in(self):
        self.replace(SYNOPSIS, "closed shop", "shut shop")
        self.assertBlocked("publishing", "synopsis.md is stale")

    def test_publishing_is_blocked_by_an_unrealized_file(self):
        os.remove(self.path(STORY_REAL))
        self.assertBlocked("publishing", "work/the-lamp.md is pending")

    def test_publishing_is_blocked_by_an_empty_story(self):
        self.write(STORY_REAL, "")
        self.run_wrist("stamp", "wrist", STORY_REAL)
        self.assertBlocked("publishing", "work/the-lamp.md is empty")

    def test_publishing_needs_the_review_pass(self):
        self.replace(PREMISE, "review_done: yes\n", "")
        self.assertBlocked("publishing", "review pass")

    def test_publishing_needs_an_author(self):
        self.replace(PREMISE, "author: Ada Example\n", "")
        self.assertBlocked("publishing", "author")

    def test_unknown_phase_is_rejected(self):
        code, out = self.gate("printing")
        self.assertEqual(code, 2, out)


if __name__ == "__main__":
    unittest.main()
