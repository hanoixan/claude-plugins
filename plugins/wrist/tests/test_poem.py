import json
import os
import re
import shutil
import unittest
import zipfile

from support import P_POEM, P_PREMISE, P_STRUCTURE, PoemCase

import wrist_verse

HAVE_TOOLS = shutil.which("pandoc") and shutil.which("typst")


class Example(PoemCase):
    def test_the_example_passes_check_verse_and_the_gate(self):
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("0 errors", out)
        code, out = self.run_wrist("verse", "wrist", "--root", ".")
        self.assertEqual(code, 0, out)
        self.assertIn("0 errors, 0 estimates", out)
        code, out = self.run_wrist("gate", "wrist", "publishing", "--root", ".")
        self.assertEqual(code, 0, out)
        self.assertIn("open", out)

    def test_the_example_is_clean_under_lint(self):
        code, out = self.run_wrist("lint", "wrist", "--root", ".")
        self.assertEqual(code, 0, out)
        self.assertIn("0 hits in 0 files", out)

    def test_the_example_is_a_real_villanelle(self):
        poem = wrist_verse.parse_poem(self.read("structure.md"))
        self.assertEqual(poem.named, "villanelle")
        self.assertEqual(wrist_verse.total_lines(poem), 19)


class VerseCommand(PoemCase):
    def verse(self, *extra):
        return self.run_wrist("verse", "wrist", "--root", ".", *extra)

    def test_a_changed_refrain_is_an_error_and_blocks_the_gate(self):
        self.replace("work/counting.md", "Some lids have rusted shut. I never find,\nthe same count twice. I stoop. The light is low.\nI count the jars my mother left behind.",
                     "Some lids have rusted shut. I never find,\nthe same count twice. I stoop. The light is low.\nI count the jars my mother left ahead.")
        code, out = self.verse()
        self.assertEqual(code, 1, out)
        self.assertIn("work/counting.md:9: error: R8: line 6 must repeat line 1 (refrain R1) word for word", out)
        self.run_wrist("stamp", "wrist", "work/counting.md", "--root", ".")
        code, out = self.run_wrist("gate", "wrist", "publishing", "--root", ".")
        self.assertEqual(code, 1, out)
        self.assertIn("work/counting.md:9: R8: line 6 must repeat line 1", out)

    def test_estimates_never_fail_the_command_or_the_gate(self):
        self.replace("work/counting.md", "forty in the cellar's dark, row on row,", "forty in the dark, row on row,")
        code, out = self.verse()
        self.assertEqual(code, 0, out)
        self.assertIn("estimate: about 8 syllables, the skeleton asks for 10 to 11 (estimate)", out)
        self.assertIn("0 errors, 1 estimates", out)
        self.run_wrist("stamp", "wrist", "work/counting.md", "--root", ".")
        code, out = self.run_wrist("gate", "wrist", "publishing", "--root", ".")
        self.assertEqual(code, 0, out)

    def test_a_syntax_error_in_the_skeleton_names_line_and_column(self):
        self.replace("structure.md", "refrain R1 at 1, 6, 12, 18;", "refrain R1 at 1, 6, 12, 18")
        code, out = self.verse()
        self.assertEqual(code, 1, out)
        self.assertRegex(out, r"structure\.md:4: error: column \d+: expected ';', found 'refrain'")

    def test_a_skeleton_rule_failure(self):
        self.replace("structure.md", "refrain R2 at 3, 9, 15, 19;", "refrain R2 at 3, 9, 15, 29;")
        code, out = self.verse()
        self.assertEqual(code, 1, out)
        self.assertIn("structure.md:4: error: R8: refrain R2: line 29 is outside the poem (it has 19 lines)", out)

    def test_the_stand_in_must_agree_with_the_skeleton(self):
        self.replace(P_STRUCTURE, "- **Form:** villanelle", "- **Form:** sestina")
        self.replace(P_STRUCTURE, "- **Lines:** 19", "- **Lines:** 20")
        self.replace(P_STRUCTURE, "- **Stanzas:** 6", "- **Stanzas:** 5")
        code, out = self.verse()
        self.assertEqual(code, 1, out)
        self.assertIn("`Form:` says 'sestina' but structure.md says 'villanelle'", out)
        self.assertIn("`Lines:` says 20 but structure.md has 19", out)
        self.assertIn("`Stanzas:` says 5 but structure.md has 6", out)

    def test_a_form_that_is_not_in_the_catalog(self):
        self.replace("structure.md", 'named "villanelle"', 'named "sapphic"')
        code, out = self.verse()
        self.assertEqual(code, 1, out)
        self.assertIn("named form 'sapphic' is not in the catalog (ballad, blank-verse", out)

    def test_a_skeleton_that_departs_from_its_named_form(self):
        self.replace("structure.md", "refrain R2 at 3, 9, 15, 19;\n", "")
        code, out = self.verse()
        self.assertEqual(code, 1, out)
        self.assertIn("named form villanelle: the refrains differ", out)

    def test_the_title_line_must_match_titled(self):
        self.replace(P_PREMISE, "titled: yes", "titled: no")
        code, out = self.verse()
        self.assertEqual(code, 1, out)
        self.assertIn("the poem has a title line but PREMISE.md says `titled: no`", out)

    def test_json_output(self):
        self.replace("work/counting.md", "forty in the cellar's dark, row on row,", "forty in the dark, row on row,")
        code, out = self.verse("--json")
        self.assertEqual(code, 0, out)
        data = json.loads(out)
        self.assertEqual([(d["severity"], d["file"], d["line"]) for d in data], [("estimate", "work/counting.md", 4)])

    def test_a_missing_poem_is_reported_and_the_skeleton_is_still_checked(self):
        os.remove(self.path("work/counting.md"))
        code, out = self.verse()
        self.assertEqual(code, 1, out)
        self.assertIn("work/counting.md:1: error: the file does not exist yet; realize it first", out)
        self.assertIn("1 errors, 0 estimates", out)
        self.replace("structure.md", "refrain R2 at 3, 9, 15, 19;", "refrain R2 at 3, 9, 15, 29;")
        code, out = self.verse()
        self.assertIn("structure.md:4: error: R8: refrain R2: line 29 is outside the poem", out)
        self.assertIn("work/counting.md:1: error: the file does not exist yet", out)

    def test_a_missing_skeleton_is_reported(self):
        os.remove(self.path("structure.md"))
        code, out = self.verse()
        self.assertEqual(code, 1, out)
        self.assertIn("structure.md:1: error: the file does not exist yet; realize it first", out)

    def test_a_skeleton_with_rule_errors_leaves_the_poem_unchecked(self):
        self.replace("structure.md", "refrain R2 at 3, 9, 15, 19;", "refrain R2 at 3, 9, 15, 29;")
        code, out = self.verse()
        self.assertIn("work/counting.md:1: error: the poem was not checked: fix the errors in structure.md first", out)

    def test_a_profile_without_a_form_refuses(self):
        code, out = self.run_wrist("verse", "wrist", "--profile", "shortstory", "--root", ".")
        self.assertNotEqual(code, 0)
        self.assertIn("has no poem form", out)


@unittest.skipUnless(HAVE_TOOLS, "pandoc and typst are not installed")
class RealBuild(PoemCase):
    def publish(self):
        code, out = self.run_wrist("publish", "wrist", "--root", ".")
        self.assertEqual(code, 0, out)
        self.assertIn("published output/counting.epub and output/counting.pdf", out)

    def epub(self, name):
        with zipfile.ZipFile(self.path("output/counting.epub")) as z:
            return z.read(name).decode("utf-8")

    def test_a_titled_poem_builds_a_pdf_and_an_epub_with_one_contents_entry(self):
        self.publish()
        with open(self.path("output/counting.pdf"), "rb") as fh:
            self.assertEqual(fh.read(5), b"%PDF-")
        nav = self.epub("EPUB/nav.xhtml")
        self.assertEqual(re.findall(r"<a [^>]*>([^<]*)</a>", nav), ["Counting"])
        self.assertIn('id="poem-title"', self.epub("EPUB/text/ch001.xhtml"))
        self.assertEqual(len([n for n in zipfile.ZipFile(self.path("output/counting.epub")).namelist() if n.endswith(".xhtml")]), 2)

    def test_the_epub_keeps_every_line_and_stanza(self):
        self.publish()
        page = self.epub("EPUB/text/ch001.xhtml")
        self.assertEqual(page.count('<div class="stanza">'), 6)
        self.assertIn("I count the jars my mother left behind,<br />", page)
        self.assertIn("for my mother", page)

    def test_an_untitled_poem_hides_its_working_title_in_the_epub(self):
        self.replace(P_PREMISE, "titled: yes", "titled: no")
        self.write("work/counting.md", self.read("work/counting.md").split("\n", 2)[2])
        self.run_wrist("stamp", "wrist", "work/counting.md", "--root", ".")
        self.publish()
        self.assertIn('id="poem-hidden-title"', self.epub("EPUB/text/ch001.xhtml"))
        self.assertIn("poem-hidden-title > h1", self.epub("EPUB/styles/stylesheet1.css"))

    def test_special_characters_in_the_title_and_epigraph_build(self):
        self.replace(P_PREMISE, "title: Counting", 'title: A & B #1 @home "Q"')
        self.replace(P_PREMISE, "dedication: for my mother", 'dedication: for M. & $5 @x')
        self.replace("work/counting.md", "# Counting", '# A & B #1 @home "Q"')
        self.run_wrist("stamp", "wrist", "work/counting.md", "--root", ".")
        self.publish()
        self.assertIn("A &amp; B #1 @home", self.epub("EPUB/text/ch001.xhtml"))
