import os
import shutil
import tempfile
import unittest
import zipfile

from support import NovelCase, PREMISE, SKILL, TreeCase     # first: it puts the scripts folder on sys.path

import wrist_publish

HAVE_TOOLS = shutil.which("pandoc") and shutil.which("typst")
PUBLISH_DIR = os.path.join(SKILL, "publish")


class PlanCommands(unittest.TestCase):
    META = {"title": "The Lamp", "author": "Ada Example", "language": "en"}

    def plan(self, **meta):
        return dict(wrist_publish.plan_commands(["work/the-lamp.md"], dict(self.META, **meta),
                                                "output", "the-lamp", PUBLISH_DIR))

    def test_both_formats_are_planned_into_output(self):
        plan = self.plan()
        self.assertEqual(set(plan), {"epub", "pdf"})
        self.assertIn("output/the-lamp.epub", plan["epub"])
        self.assertIn("output/the-lamp.pdf", plan["pdf"])

    def test_pandoc_builds_both_and_typst_makes_the_pdf(self):
        plan = self.plan()
        self.assertEqual(plan["epub"][0], "pandoc")
        self.assertEqual(plan["pdf"][0], "pandoc")
        self.assertIn("--pdf-engine=typst", plan["pdf"])
        self.assertIn(os.path.join(PUBLISH_DIR, "book.typ"), plan["pdf"])
        self.assertIn(os.path.join(PUBLISH_DIR, "epub.css"), plan["epub"])

    def test_sources_are_passed_in_order(self):
        cmds = wrist_publish.plan_commands(["work/a.md", "work/b.md"], self.META, "output", "x", PUBLISH_DIR)
        argv = dict(cmds)["epub"]
        self.assertLess(argv.index("work/a.md"), argv.index("work/b.md"))

    def test_a_title_with_quotes_ampersand_and_unicode_is_one_intact_argument(self):
        title = 'The "Lamp" & Co. — café été'
        for argv in self.plan(title=title).values():
            self.assertIn(f"title={title}", argv)

    def test_language_defaults_to_english(self):
        plan = wrist_publish.plan_commands(["a.md"], {"title": "T", "author": "A"}, "output", "t", PUBLISH_DIR)
        self.assertIn("lang=en", dict(plan)["epub"])

    def test_trim_and_font_reach_the_pdf_only(self):
        plan = self.plan(trim="us-trade", font="Linux Libertine")
        self.assertIn("papersize=us-trade", plan["pdf"])
        self.assertIn("mainfont=Linux Libertine", plan["pdf"])
        self.assertNotIn("papersize=us-trade", plan["epub"])


class TitlePage(unittest.TestCase):
    META = {"title": "The Lamp", "author": "Ada Example", "language": "en"}

    def plan(self, **meta):
        return dict(wrist_publish.plan_commands(["work/the-lamp.md"], dict(self.META, **meta),
                                                "output", "the-lamp", PUBLISH_DIR))

    def test_a_title_page_is_the_default(self):
        plan = self.plan()
        self.assertNotIn("--epub-title-page=false", plan["epub"])
        self.assertNotIn("no-title-page=true", plan["pdf"])
        self.assertNotIn("--lua-filter", plan["epub"] + plan["pdf"])

    def test_without_a_title_page_both_formats_drop_it_and_add_a_byline(self):
        plan = self.plan(title_page=False)
        self.assertIn("--epub-title-page=false", plan["epub"])
        self.assertIn("no-title-page=true", plan["pdf"])
        byline = os.path.join(PUBLISH_DIR, "byline.lua")
        for argv in plan.values():
            self.assertEqual(argv[argv.index("--lua-filter") + 1], byline)
        self.assertTrue(os.path.isfile(byline))

    def test_the_template_can_leave_the_title_page_out(self):
        with open(os.path.join(PUBLISH_DIR, "book.typ"), encoding="utf-8") as fh:
            self.assertIn("$if(no-title-page)$", fh.read())


class TemplateHelpers(unittest.TestCase):
    """Pandoc emits `#divider()` for a scene break (3.12; `#horizontalrule` in older versions)."""

    def test_the_template_defines_every_helper_pandoc_may_emit(self):
        with open(os.path.join(PUBLISH_DIR, "book.typ"), encoding="utf-8") as fh:
            template = fh.read()
        for helper in ("#let divider()", "#let horizontalRule", "#let horizontalrule"):
            self.assertIn(helper, template)

    @unittest.skipUnless(HAVE_TOOLS, "pandoc and typst are not installed")
    def test_a_scene_break_is_drawn_as_asterisks_not_a_rule(self):
        d = tempfile.mkdtemp(prefix="wrist-typ-")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        import subprocess
        with open(os.path.join(d, "a.md"), "w", encoding="utf-8") as fh:
            fh.write("One.\n\n* * *\n\nTwo.\n")
        out = subprocess.run(["pandoc", "a.md", "-M", "title=T", "-M", "author=A", "--pdf-engine=typst",
                              "--template", os.path.join(PUBLISH_DIR, "book.typ"), "-t", "typst"],
                             cwd=d, capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("#divider()", out.stdout)
        self.assertIn("#let divider()", out.stdout)


class BookPlan(unittest.TestCase):
    META = {"title": "Salt Road", "author": "Ada Example", "language": "en", "title_page": True}

    def plan(self, **meta):
        return dict(wrist_publish.plan_commands(["work/forward.md", "work/chapter-1.md"],
                                                dict(self.META, **meta), "output", "salt-road", PUBLISH_DIR))

    def test_a_book_without_front_matter_has_no_filter_and_no_contents_flags(self):
        plan = self.plan()
        self.assertNotIn("--lua-filter", plan["epub"] + plan["pdf"])
        self.assertNotIn("--toc", plan["epub"])
        self.assertNotIn("front-matter=true", plan["pdf"])

    def test_front_matter_adds_the_filter_the_contents_and_the_numbering_switch(self):
        plan = self.plan(front_matter=True)
        filt = os.path.join(PUBLISH_DIR, "frontmatter.lua")
        for argv in plan.values():
            self.assertEqual(argv[argv.index("--lua-filter") + 1], filt)
        self.assertIn("--toc", plan["epub"])
        self.assertIn("front-matter=true", plan["pdf"])
        self.assertIn("wrist-contents=true", plan["pdf"])
        self.assertTrue(os.path.isfile(filt))

    def test_copyright_dedication_and_epigraph_reach_both_formats(self):
        plan = self.plan(front_matter=True, copyright="(c) 2026", dedication="For X", epigraph="Q")
        for argv in plan.values():
            for item in ("copyright=(c) 2026", "dedication=For X", "epigraph=Q"):
                self.assertIn(item, argv)

    def test_review_focus_special_characters_stay_one_intact_argument(self):
        text = 'A & B #1 — "Q" café © 2026 *x* _y_'
        plan = self.plan(front_matter=True, copyright=text, dedication=text, epigraph=text)
        for argv in plan.values():
            for key in ("copyright", "dedication", "epigraph"):
                self.assertIn(f"{key}={text}", argv)

    def test_unset_front_matter_keys_are_not_passed(self):
        plan = self.plan(front_matter=True)
        self.assertFalse([a for a in plan["epub"] if a.startswith(("copyright=", "dedication=", "epigraph="))])

    def test_the_byline_filter_and_the_front_matter_filter_can_both_apply(self):
        plan = self.plan(front_matter=True, title_page=False)
        filters = [plan["epub"][i + 1] for i, a in enumerate(plan["epub"]) if a == "--lua-filter"]
        self.assertEqual(len(filters), 2)


class Marker(unittest.TestCase):
    def setUp(self):
        self.cwd = tempfile.mkdtemp(prefix="wrist-mark-")
        self.addCleanup(shutil.rmtree, self.cwd, ignore_errors=True)

    def test_the_marker_is_inserted_before_the_first_body_file(self):
        inputs, marker = wrist_publish.with_marker(["work/forward.md", "work/chapter-1.md", "work/chapter-2.md"],
                                                   "work/chapter-1.md", "output", self.cwd)
        self.assertEqual(inputs, ["work/forward.md", "output/.wrist-body.md", "work/chapter-1.md",
                                  "work/chapter-2.md"])
        self.assertEqual(marker, "output/.wrist-body.md")
        with open(os.path.join(self.cwd, marker), encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("#in-body.update(true)", text)
        self.assertIn('#set page(numbering: "1")', text)
        self.assertIn("#counter(page).update(1)", text)

    def test_no_first_body_file_means_no_marker(self):
        inputs, marker = wrist_publish.with_marker(["work/a.md"], None, "output", self.cwd)
        self.assertEqual((inputs, marker), (["work/a.md"], None))
        self.assertFalse(os.path.exists(os.path.join(self.cwd, "output")))

    def test_remove_marker_deletes_the_file_and_tolerates_none(self):
        _, marker = wrist_publish.with_marker(["c.md"], "c.md", "output", self.cwd)
        wrist_publish.remove_marker(marker, self.cwd)
        self.assertFalse(os.path.exists(os.path.join(self.cwd, marker)))
        wrist_publish.remove_marker(None, self.cwd)
        wrist_publish.remove_marker(marker, self.cwd)


class NovelBuild(NovelCase):
    @unittest.skipUnless(HAVE_TOOLS, "pandoc and typst are not installed")
    def test_the_novel_publishes_with_front_matter_and_a_contents_page(self):
        code, out = self.run_wrist("publish", "wrist")
        self.assertEqual(code, 0, out)
        with open(self.path("output/salt-road.pdf"), "rb") as fh:
            self.assertEqual(fh.read(5), b"%PDF-")
        with zipfile.ZipFile(self.path("output/salt-road.epub")) as z:
            names = z.namelist()
            opf = z.read("EPUB/content.opf").decode("utf-8")
            html = {n: z.read(n).decode("utf-8") for n in names if n.endswith(".xhtml")}
        self.assertTrue([n for n in names if "title_page" in n])
        self.assertIn('idref="nav"', opf)                                   # a visible contents page
        text = "\n".join(html.values())
        for needle in ("For the carters.", "Salt keeps what it is given.", "All rights reserved.",
                       "Foreword", "1. The Load", "2. The Toll", "3. The Gate"):
            self.assertIn(needle, text, needle)
        self.assertGreaterEqual(len([n for n in names if n.startswith("EPUB/text/ch")]), 4)   # front matter, forward, chapters
        self.assertNotIn("PREMISE", text)

    @unittest.skipUnless(HAVE_TOOLS, "pandoc and typst are not installed")
    def test_no_generated_files_are_left_behind(self):
        self.run_wrist("publish", "wrist")
        self.assertEqual(sorted(os.listdir(self.path("output"))), ["salt-road.epub", "salt-road.pdf"])

    @unittest.skipUnless(HAVE_TOOLS, "pandoc and typst are not installed")
    def test_a_failed_build_still_removes_the_marker(self):
        self.write("work/chapter-2.md", "# 2. The Toll\n\n" + "\x00" * 3 + "\n")
        self.run_wrist("stamp", "wrist", "work/chapter-2.md")
        self.run_wrist("publish", "wrist")
        self.assertFalse(os.path.exists(self.path("output/.wrist-body.md")))

    @unittest.skipUnless(HAVE_TOOLS, "pandoc and typst are not installed")
    def test_review_focus_special_characters_render(self):
        self.replace("wrist/PREMISE.md", "dedication: For the carters.", 'dedication: A & B #1 "Q" — café')
        code, out = self.run_wrist("publish", "wrist")
        self.assertEqual(code, 0, out)
        with zipfile.ZipFile(self.path("output/salt-road.epub")) as z:
            text = "\n".join(z.read(n).decode("utf-8") for n in z.namelist() if n.endswith(".xhtml"))
        self.assertIn("A &amp; B #1", text)
        self.assertIn("café", text)


class InstallHelp(unittest.TestCase):
    def test_help_names_each_missing_tool(self):
        text = wrist_publish.install_help(["pandoc", "typst"])
        self.assertIn("pandoc", text)
        self.assertIn("typst", text)
        self.assertIn("https://", text)

    def test_help_for_one_tool_does_not_mention_the_other(self):
        self.assertNotIn("typst", wrist_publish.install_help(["pandoc"]))

    def test_missing_tools_honours_the_path(self):
        empty = tempfile.mkdtemp(prefix="wrist-path-")
        self.addCleanup(shutil.rmtree, empty, ignore_errors=True)
        self.assertEqual(wrist_publish.missing_tools(empty), ["pandoc", "typst"])


class PublishCommand(TreeCase):
    def publish(self, env=None):
        return self.run_wrist("publish", "wrist", env=env)

    def empty_path_env(self):
        empty = tempfile.mkdtemp(prefix="wrist-path-")
        self.addCleanup(shutil.rmtree, empty, ignore_errors=True)
        return dict(os.environ, PATH=empty)

    def test_gate_blockers_are_listed_and_nothing_is_built(self):
        self.replace(PREMISE, "review_done: yes\n", "")
        code, out = self.publish(self.empty_path_env())
        self.assertEqual(code, 1, out)
        self.assertIn("publish blocked", out)
        self.assertIn("review pass", out)
        self.assertFalse(os.path.exists(self.path("output")))

    def test_missing_tools_stop_with_install_steps(self):
        code, out = self.publish(self.empty_path_env())
        self.assertEqual(code, 1, out)
        self.assertIn("pandoc", out)
        self.assertIn("typst", out)
        self.assertIn("https://", out)
        self.assertFalse(os.path.exists(self.path("output")))

    @unittest.skipUnless(HAVE_TOOLS, "pandoc and typst are not installed")
    def test_real_build_writes_both_files(self):
        code, out = self.publish()
        self.assertEqual(code, 0, out)
        with open(self.path("output/the-lamp.pdf"), "rb") as fh:
            self.assertEqual(fh.read(5), b"%PDF-")
        with zipfile.ZipFile(self.path("output/the-lamp.epub")) as z:
            self.assertEqual(z.namelist()[0], "mimetype")
            text = "".join(z.read(n).decode("utf-8", "replace") for n in z.namelist() if n.endswith(".xhtml"))
        self.assertIn("The sign in the window said closed", text)
        self.assertNotIn("Referred by", text)
        self.assertNotIn("PREMISE", text)

    @unittest.skipUnless(HAVE_TOOLS, "pandoc and typst are not installed")
    def test_a_short_story_epub_has_its_heading_and_a_byline_but_no_title_page(self):
        self.publish()
        with zipfile.ZipFile(self.path("output/the-lamp.epub")) as z:
            names = z.namelist()
            chapter = z.read("EPUB/text/ch001.xhtml").decode("utf-8")
        self.assertFalse([n for n in names if "title_page" in n], names)
        self.assertIn("<h1>The Lamp</h1>", chapter)
        self.assertRegex(chapter, r'<div class="byline">\s*<p>Ada Example</p>')

    @unittest.skipUnless(HAVE_TOOLS, "pandoc and typst are not installed")
    def test_a_title_page_is_still_built_when_asked_for(self):
        plan = wrist_publish.plan_commands(["work/the-lamp.md"],
                                           {"title": "The Lamp", "author": "Ada Example", "title_page": True},
                                           "output", "the-lamp", PUBLISH_DIR)
        wrist_publish.run_commands(plan, self.dir)
        with zipfile.ZipFile(self.path("output/the-lamp.epub")) as z:
            self.assertTrue([n for n in z.namelist() if "title_page" in n])


if __name__ == "__main__":
    unittest.main()
