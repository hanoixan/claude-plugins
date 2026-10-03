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


if __name__ == "__main__":
    unittest.main()
