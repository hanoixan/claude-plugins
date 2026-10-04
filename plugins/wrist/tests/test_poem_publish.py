import os
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
