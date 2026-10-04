import os
import re
import shutil
import subprocess
import tempfile
import unittest

from support import SKILL

import wrist_profile as wp
import wrist_publish


class PoemPlan(unittest.TestCase):
    META = {"title": "Counting", "author": "Ada Example", "language": "en"}
    PUBLISH_DIR = os.path.join(SKILL, "publish")

    def plan(self, **meta):
        return dict(wrist_publish.plan_poem(["work/counting.md"], dict(self.META, **meta), "output", "counting", self.PUBLISH_DIR))

    def test_the_style_resolves(self):
        self.assertEqual(wrist_publish.style_for(wp.load_profile("poem")), "poem")

    def test_both_formats_read_verse_through_the_custom_reader_and_filter(self):
        d = os.path.join(self.PUBLISH_DIR, "poem")
        for argv in self.plan().values():
            self.assertEqual(argv[:4], ["pandoc", "--from", os.path.join(d, "verse.lua"), "work/counting.md"])
            self.assertEqual(argv[argv.index("--lua-filter") + 1], os.path.join(d, "poem.lua"))
        for name in ("verse.lua", "poem.lua", "poem.typ", "poem.css"):
            self.assertTrue(os.path.isfile(os.path.join(d, name)), name)

    def test_the_pdf_uses_the_template_and_the_epub_the_stylesheet(self):
        d = os.path.join(self.PUBLISH_DIR, "poem")
        pdf, epub = self.plan()["pdf"], self.plan()["epub"]
        self.assertEqual(pdf[pdf.index("--template") + 1], os.path.join(d, "poem.typ"))
        self.assertIn("--pdf-engine=typst", pdf)
        self.assertEqual(epub[epub.index("--css") + 1], os.path.join(d, "poem.css"))
        self.assertIn("--epub-title-page=false", epub)

    def test_titled_dedication_and_epigraph_reach_both_formats_only_when_set(self):
        plan = self.plan(titled=True, dedication="for M.", epigraph="an epigraph")
        for argv in plan.values():
            for item in ("titled=true", "dedication=for M.", "epigraph=an epigraph"):
                self.assertIn(item, argv)
        for argv in self.plan().values():
            self.assertFalse([a for a in argv if a.startswith(("titled=", "dedication=", "epigraph="))])

    def test_review_focus_special_characters_stay_one_intact_argument(self):
        text = 'A & B #1 @home $5 "Q" café *x* \\ [w]'
        for argv in self.plan(title=text, epigraph=text, dedication=text).values():
            for key in ("title", "epigraph", "dedication"):
                self.assertIn(f"{key}={text}", argv)


HAVE_PANDOC = shutil.which("pandoc") is not None
HAVE_TYPST = shutil.which("typst") is not None


def pandoc_poem(text, to, *meta, template=True):
    d = os.path.join(SKILL, "publish", "poem")
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "p.md")
        with open(src, "w", encoding="utf-8") as fh:
            fh.write(text)
        out = os.path.join(tmp, "out." + ("pdf" if to == "pdf" else "typ"))
        argv = ["pandoc", "--from", os.path.join(d, "verse.lua"), src, "--lua-filter", os.path.join(d, "poem.lua"),
                "--template", os.path.join(d, "poem.typ")]
        argv += ["--pdf-engine=typst", "-o", out] if to == "pdf" else ["--to", "typst", "-o", out]
        for item in meta:
            argv += ["-M", item]
        proc = subprocess.run(argv, capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
        with open(out, "rb") as fh:
            return fh.read()


@unittest.skipUnless(HAVE_PANDOC, "pandoc is not installed")
class HeadingText(unittest.TestCase):
    def test_review_focus_heading_fields_are_text_not_typst_markup(self):
        typ = pandoc_poem("a line\n", "typst", "title=- item one", "author=+ Ada", "dedication== for my mother",
                          "epigraph=1. first", "titled=true").decode("utf-8")
        for escaped in ("\\- item one", "\\+ Ada", "\\= for my mother", "\\1. first"):
            self.assertIn(escaped, typ)

    def test_each_heading_element_appears_once_and_in_order(self):
        typ = pandoc_poem("a line\n", "typst", "title=T", "author=A", "dedication=D", "epigraph=E", "titled=true").decode("utf-8")
        positions = [typ.index(f"#{name}[") for name in ("poem-dedication", "poem-title", "poem-byline", "poem-epigraph")]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(typ.count("#poem-title["), 1)

    def test_an_untitled_poem_has_no_title_block(self):
        typ = pandoc_poem("a line\n", "typst", "title=T", "author=A").decode("utf-8")
        self.assertNotIn("#poem-title[", typ)
        self.assertIn("#poem-byline[", typ)


@unittest.skipUnless(HAVE_PANDOC and HAVE_TYPST, "pandoc and typst are not installed")
class TallStanzas(unittest.TestCase):
    def pages(self, pdf):
        return int(re.search(rb"/Count (\d+)", pdf).group(1))

    def test_review_focus_a_stanza_taller_than_a_page_breaks_instead_of_overflowing(self):
        long_line = " ".join(["word"] * 30)          # wraps to three lines on A5
        poem = "\n".join([long_line] * 16) + "\n\nlast\n"
        # About a page and a half: broken across two pages. Kept whole, it moved to page 2, overflowed
        # there (lines printed on top of one another) and left `last` for a third page.
        self.assertEqual(self.pages(pandoc_poem(poem, "pdf", "title=T", "author=A")), 2)

    def test_a_short_stanza_is_kept_whole(self):
        typ = pandoc_poem("a\nb\n", "typst", "title=T", "author=A").decode("utf-8")
        self.assertIn("#stanza(true)[", typ)
