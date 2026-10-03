import os
import unittest

from support import (CHARACTERS, MISC, OUTLINE, PREMISE, STORY, SYNOPSIS, TreeCase)


class CheckAcceptsTheExample(TreeCase):
    def test_pristine_example_has_no_errors_or_warnings(self):
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("5 stand-ins", out)
        self.assertIn("0 errors, 0 warnings", out)

    def test_left_over_arguments_are_rejected(self):
        code, out = self.run_wrist("check", "wrist", "extra")
        self.assertEqual(code, 2, out)
        self.assertIn("unrecognized arguments: extra", out)

    def test_crlf_files_check_clean(self):
        for rel in (SYNOPSIS, OUTLINE, CHARACTERS, MISC, STORY, PREMISE):
            with open(self.path(rel), "rb") as fh:
                data = fh.read().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
            with open(self.path(rel), "wb") as fh:
                fh.write(data)
        code, out = self.check()
        self.assertEqual(code, 0, out)


class CheckRejectsBrokenTrees(TreeCase):
    def test_deleted_backlink(self):
        self.replace(SYNOPSIS, "- **Referred by:** [outline](./outline.md.wrist.md)\n", "")
        self.assertCheckFails("missing backlink")

    def test_referred_by_without_a_matching_dependency(self):
        self.append(SYNOPSIS, "- **Referred by:** [story](./work/the-lamp.md.wrist.md)\n")
        self.assertCheckFails("is listed as referring here but has no `Depends on:` link")

    def test_link_to_a_missing_file(self):
        self.append(OUTLINE, "- **Depends on:** [gone](./gone.md.wrist.md)\n")
        self.assertCheckFails("link target does not exist")

    def test_dangling_fragment(self):
        self.replace(STORY, "#beat-the-mark-inside", "#beat-no-such-beat")
        self.assertCheckFails("fragment '#beat-no-such-beat' does not match any heading")

    def test_missing_required_field(self):
        self.replace(CHARACTERS, "- **Wants:** To be left alone with the stopped clocks.\n", "")
        self.assertCheckFails("character 'Ines Vale' is missing `Wants:`")

    def test_missing_level_one_field(self):
        self.replace(SYNOPSIS, "- **Theme:** Grief can turn a person into a closed shop.\n", "")
        self.assertCheckFails("synopsis 'The Lamp' is missing `Theme:`")

    def test_missing_common_field(self):
        self.replace(MISC, "- **Required:** always\n", "")
        self.assertCheckFails("missing `Required:`")

    def test_missing_unknowns_answer(self):
        self.replace(MISC, "- **Unknowns:** none\n", "")
        self.assertCheckFails("no *UNKNOWN* entries and no `Unknowns: none`")

    def test_wrong_level_one_heading(self):
        self.replace(SYNOPSIS, "# synopsis: The Lamp", "# outline: The Lamp")
        self.assertCheckFails("must start with `# synopsis: <name>`")

    def test_child_heading_not_declared_for_the_function(self):
        self.append(OUTLINE, "\n## scene: Extra\n")
        self.assertCheckFails("`## scene:` not allowed here")

    def test_typed_heading_too_deep(self):
        self.append(OUTLINE, "\n### beat: Deep\n")
        self.assertCheckFails("`### beat:` not allowed here")

    def test_stand_in_outside_the_shape(self):
        self.write("wrist/extra.md.wrist.md", "# synopsis: Extra\n")
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("outside the shortstory shape", out)

    def test_missing_required_stand_in(self):
        os.remove(self.path(MISC))
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("required stand-in missing: wrist/misc.md.wrist.md", out)

    def test_story_name_must_match_the_slug(self):
        self.replace(PREMISE, "slug: the-lamp", "slug: lamp")
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("required stand-in missing: wrist/work/lamp.md.wrist.md", out)
        self.assertIn("outside the shortstory shape", out)

    def test_code_fence_without_a_language_tag(self):
        self.append(MISC, "\n```\nsample\n```\n")
        self.assertCheckFails("code fence has no language tag")

    def test_front_matter_in_a_stand_in_is_a_warning(self):
        self.write(SYNOPSIS, "---\nrole: product\n---\n" + self.read(SYNOPSIS))
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("stand-ins take no front matter", out)


class CheckWarnings(TreeCase):
    def test_informal_marker(self):
        self.append(OUTLINE, "\nTODO decide the middle beat.\n")
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("informal marker 'TODO'", out)

    def test_unlisted_relation_word_is_a_warning(self):
        self.replace(OUTLINE, "[synopsis](./synopsis.md.wrist.md) (mentions)",
                     "[synopsis](./synopsis.md.wrist.md) (adores)")
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("relation word 'adores' is not one of", out)

    def test_too_much_free_prose_is_a_warning(self):
        self.replace(OUTLINE, "## beat: The mark inside\n",
                     "## beat: The mark inside\n\n" + " ".join(["word"] * 130) + "\n")
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("130 words of free prose", out)

    def test_fenced_text_does_not_count_as_prose(self):
        self.replace(OUTLINE, "## beat: The mark inside\n",
                     "## beat: The mark inside\n\n```text\n" + " ".join(["word"] * 130) + "\n```\n")
        code, out = self.check()
        self.assertIn("0 errors, 0 warnings", out)


class LenientMode(TreeCase):
    def test_missing_field_is_a_warning_when_lenient(self):
        self.replace(CHARACTERS, "- **Wants:** To be left alone with the stopped clocks.\n", "")
        code, out = self.check("--lenient")
        self.assertEqual(code, 0, out)
        self.assertIn("warning: character 'Ines Vale' is missing `Wants:`", out)

    def test_broken_link_still_fails_when_lenient(self):
        self.append(OUTLINE, "- **Depends on:** [gone](./gone.md.wrist.md)\n")
        code, out = self.check("--lenient")
        self.assertEqual(code, 1, out)


class PremiseRules(TreeCase):
    def test_missing_premise_without_a_profile_flag_stops(self):
        os.remove(self.path(PREMISE))
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("no profile", out)

    def test_missing_premise_with_a_profile_flag_is_an_error(self):
        os.remove(self.path(PREMISE))
        code, out = self.run_wrist("check", "wrist", "--profile", "shortstory")
        self.assertEqual(code, 1, out)
        self.assertIn("PREMISE.md is missing", out)

    def test_profile_flag_overrides_the_premise(self):
        self.replace(PREMISE, "profile: shortstory\n", "")
        code, out = self.run_wrist("check", "wrist", "--profile", "shortstory")
        self.assertEqual(code, 0, out)

    def test_unknown_profile_name(self):
        self.replace(PREMISE, "profile: shortstory", "profile: sonnet")
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("no profile 'sonnet'", out)

    def test_title_is_required(self):
        self.replace(PREMISE, "title: The Lamp\n", "")
        self.assertCheckFails("front matter needs `title:`")

    def test_slug_must_be_lower_case_words(self):
        self.replace(PREMISE, "slug: the-lamp", "slug: The_Lamp")
        self.assertCheckFails("slug 'The_Lamp' must be lower-case words joined by hyphens")

    def test_required_question_must_be_answered(self):
        self.replace(PREMISE, "- **genre:** Literary fiction, quiet realism.\n", "")
        self.assertCheckFails("question 'genre'")

    def test_deferrable_question_unanswered_is_a_warning(self):
        self.replace(PREMISE, "- **avoid:** Naming the grief, flashbacks, weather openings.\n", "")
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("warning: question 'avoid'", out)

    def test_an_unknown_answers_a_question(self):
        self.replace(PREMISE, "- **genre:** Literary fiction, quiet realism.",
                     "- **genre:** *UNKNOWN*: [genre-pick] Which genre. Kind: blocking. Consequence: c. Unlocks: u.")
        code, out = self.check()
        self.assertEqual(code, 0, out)

    def test_broken_link_in_the_premise(self):
        self.append(PREMISE, "\nSee [gone](./gone.md.wrist.md).\n")
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("PREMISE.md", out)
        self.assertIn("link target does not exist", out)

    def test_dangling_fragment_in_the_premise(self):
        self.append(PREMISE, "\nSee [x](./outline.md.wrist.md#beat-nope).\n")
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("fragment '#beat-nope' does not match any heading", out)

    def test_links_inside_fences_in_the_premise_are_ignored(self):
        self.append(PREMISE, "\n```text\n[gone](./gone.md.wrist.md)\n```\n")
        code, out = self.check()
        self.assertEqual(code, 0, out)


class TitleAndSlug(TreeCase):
    def test_a_slug_that_is_not_the_form_of_the_title_is_a_warning(self):
        self.replace(PREMISE, "title: The Lamp", "title: The Lantern")
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("warning: slug 'the-lamp' is not the file-friendly form of the title 'The Lantern'", out)

    def test_a_title_with_accents_can_have_a_matching_slug(self):
        self.replace(PREMISE, "title: The Lamp", "title: Caf\u00e9 \u00c9t\u00e9")
        self.replace(PREMISE, "slug: the-lamp", "slug: cafe-ete")
        os.rename(self.path(STORY), self.path("wrist/work/cafe-ete.md.wrist.md"))
        self.replace("wrist/work/cafe-ete.md.wrist.md", "# story: The Lamp", "# story: Cafe Ete")
        for rel in (OUTLINE, CHARACTERS, MISC):
            self.write(rel, self.read(rel).replace("work/the-lamp.md.wrist.md", "work/cafe-ete.md.wrist.md"))
        code, out = self.check()
        self.assertNotIn("file-friendly form", out)


class FrontMatterValues(unittest.TestCase):
    def test_values_reach_the_tool_as_written(self):
        import wrist_check
        for raw, want in [("Room #9", "Room #9"), ('"Room #9"', "Room #9"), ("'x'", "x"),
                          ('"Lamp" and "Wick"', '"Lamp" and "Wick"'), ("Ines #2: Return", "Ines #2: Return"),
                          ("  plain  ", "plain")]:
            self.assertEqual(wrist_check.meta_value(raw), want, raw)


class ReadFailures(TreeCase):
    def assertClean(self, code, out, fragment):
        self.assertNotEqual(code, 0, out)
        self.assertNotIn("Traceback", out)
        self.assertIn(fragment, out)

    def test_a_stand_in_that_is_not_utf8_names_the_file(self):
        with open(self.path(MISC), "wb") as fh:
            fh.write(b"# misc: \xff\xfe\n")
        code, out = self.check()
        self.assertClean(code, out, "misc.md.wrist.md")
        self.assertIn("cannot read", out)

    def test_a_premise_that_is_not_utf8(self):
        with open(self.path(PREMISE), "wb") as fh:
            fh.write(b"---\nprofile: \xff\n---\n")
        code, out = self.check()
        self.assertClean(code, out, "cannot read")

    def test_a_premise_that_is_a_directory(self):
        os.remove(self.path(PREMISE))
        os.mkdir(self.path(PREMISE))
        code, out = self.check()
        self.assertClean(code, out, "cannot read")

    def test_unclosed_premise_front_matter_gets_its_own_message(self):
        self.replace(PREMISE, "review_done: yes\n---\n", "review_done: yes\n")
        code, out = self.check()
        self.assertNotEqual(code, 0, out)
        self.assertIn("front matter is not closed", out)
        self.assertNotIn("no profile: give", out)

    def test_a_missing_wrist_folder_says_so(self):
        code, out = self.run_wrist("check", "nowhere")
        self.assertNotEqual(code, 0, out)
        self.assertIn("not a directory: nowhere", out)


if __name__ == "__main__":
    unittest.main()
