import os
import shutil
import tempfile
import unittest
import zipfile

from support import PREMISE, SKILL, TreeCase     # first: it puts the scripts folder on sys.path

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
