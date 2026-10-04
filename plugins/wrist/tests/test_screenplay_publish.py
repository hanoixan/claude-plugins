import os
import shutil
import subprocess
import tempfile
import unittest
import zipfile

from support import SKILL     # first: it puts the scripts folder on sys.path

import wrist_profile
import wrist_publish

HAVE_TOOLS = shutil.which("pandoc") and shutil.which("typst")
PUBLISH_DIR = os.path.join(SKILL, "publish")
SCRIPT = ("INT. FERRY DECK - NIGHT\n\nMARIT counts faces with a clipboard.\n\nMARIT\n(quietly)\nTwenty-three.\n\n"
          "CUT TO:\n\nEXT. SEA GATE - DUSK\n\n> THE END <\n")


def fake_profile(**extra):
    data = {"name": "t", "files": [{"path": "a.md", "function": "a", "order": 1}],
            "functions": {"a": {"heading": "a", "prose": True}}, "relations": [], "limits": {"max_prose_words": 5}}
    data.update(extra)
    return wrist_profile.parse_profile(data)


class StyleResolution(unittest.TestCase):
    def test_an_explicit_style_wins(self):
        self.assertEqual(wrist_publish.style_for(fake_profile(publish={"style": "screenplay"})), "screenplay")

    def test_without_a_publish_key_the_style_is_inferred_as_before(self):
        self.assertEqual(wrist_publish.style_for(wrist_profile.load_profile("shortstory")), "story")
        self.assertEqual(wrist_publish.style_for(wrist_profile.load_profile("novel")), "book")

    def test_an_unknown_style_names_the_known_ones(self):
        with self.assertRaises(wrist_publish.PublishError) as cm:
            wrist_publish.style_for(fake_profile(publish={"style": "poster"}))
        self.assertIn("unknown publishing style 'poster'", str(cm.exception))
        self.assertIn("story, book, screenplay", str(cm.exception))


class ScreenplayPlan(unittest.TestCase):
    META = {"title": "The Third Bell", "author": "Sam Rivers", "language": "en"}

    def plan(self, **meta):
        return dict(wrist_publish.plan_screenplay(["work/act-1.md", "work/act-2.md"], dict(self.META, **meta),
                                                  "output", "the-third-bell", PUBLISH_DIR))

    def test_both_formats_read_fountain_through_the_custom_reader(self):
        reader = os.path.join(PUBLISH_DIR, "screenplay", "fountain.lua")
        for argv in self.plan().values():
            self.assertEqual(argv[:3], ["pandoc", "--from", reader])
            self.assertLess(argv.index("work/act-1.md"), argv.index("work/act-2.md"))
        self.assertTrue(os.path.isfile(reader))

    def test_the_pdf_uses_the_screenplay_template_and_filter(self):
        argv = self.plan()["pdf"]
        d = os.path.join(PUBLISH_DIR, "screenplay")
        self.assertIn("--pdf-engine=typst", argv)
        self.assertEqual(argv[argv.index("--template") + 1], os.path.join(d, "screenplay.typ"))
        self.assertEqual(argv[argv.index("--lua-filter") + 1], os.path.join(d, "screenplay.lua"))
        self.assertIn("output/the-third-bell.pdf", argv)

    def test_the_epub_uses_the_stylesheet_and_the_same_filter(self):
        argv = self.plan()["epub"]
        d = os.path.join(PUBLISH_DIR, "screenplay")
        self.assertEqual(argv[argv.index("--css") + 1], os.path.join(d, "screenplay.css"))
        self.assertEqual(argv[argv.index("--lua-filter") + 1], os.path.join(d, "screenplay.lua"))
        self.assertIn("epub3", argv)

    def test_title_page_keys_reach_both_formats_only_when_set(self):
        plan = self.plan(based_on="A short story", draft="First draft", contact="sam@example.com")
        for argv in plan.values():
            for item in ("based_on=A short story", "draft=First draft", "contact=sam@example.com"):
                self.assertIn(item, argv)
        self.assertFalse([a for a in self.plan()["pdf"] if a.startswith(("based_on=", "draft=", "contact="))])

    def test_review_focus_special_characters_stay_one_intact_argument(self):
        text = 'A & B #1 — "Q" café *x*'
        plan = self.plan(title=text, based_on=text, contact=text)
        for argv in plan.values():
            for key in ("title", "based_on", "contact"):
                self.assertIn(f"{key}={text}", argv)

    def test_trim_and_font_reach_the_pdf_only(self):
        plan = self.plan(trim="a4", font="Courier Prime")
        self.assertIn("papersize=a4", plan["pdf"])
        self.assertIn("mainfont=Courier Prime", plan["pdf"])
        self.assertNotIn("papersize=a4", plan["epub"])

    def test_no_smart_punctuation_extension_is_requested(self):
        for argv in self.plan().values():
            self.assertFalse([a for a in argv if "+smart" in a])


class ActMarkers(unittest.TestCase):
    def setUp(self):
        self.cwd = tempfile.mkdtemp(prefix="wrist-acts-")
        self.addCleanup(shutil.rmtree, self.cwd, ignore_errors=True)

    def test_a_marker_goes_before_each_act_file(self):
        sources = ["work/act-1.md", "work/act-2.md", "work/act-3.md"]
        inputs, markers = wrist_publish.with_act_markers(sources, sources, "output", self.cwd)
        self.assertEqual(inputs, ["output/.wrist-act-1.md", "work/act-1.md", "output/.wrist-act-2.md",
                                  "work/act-2.md", "output/.wrist-act-3.md", "work/act-3.md"])
        for n, word in enumerate(("ONE", "TWO", "THREE"), 1):
            with open(os.path.join(self.cwd, f"output/.wrist-act-{n}.md"), encoding="utf-8") as fh:
                self.assertEqual(fh.read(), f"@@ACT {word}@@\n")
        self.assertEqual(len(markers), 3)

    def test_remove_markers_deletes_them_and_tolerates_missing_ones(self):
        _, markers = wrist_publish.with_act_markers(["a.md"], ["a.md"], "output", self.cwd)
        wrist_publish.remove_markers(markers, self.cwd)
        self.assertFalse(os.path.exists(os.path.join(self.cwd, markers[0])))
        wrist_publish.remove_markers(markers, self.cwd)
        wrist_publish.remove_markers([], self.cwd)

    def test_seven_acts_have_names(self):
        self.assertEqual(wrist_publish.NUMBER_WORDS, ("ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN"))


@unittest.skipUnless(HAVE_TOOLS, "pandoc and typst are not installed")
class RealBuilds(unittest.TestCase):
    def setUp(self):
        self.cwd = tempfile.mkdtemp(prefix="wrist-sp-")
        self.addCleanup(shutil.rmtree, self.cwd, ignore_errors=True)
        os.makedirs(os.path.join(self.cwd, "work"))
        with open(os.path.join(self.cwd, "work", "act-1.md"), "w", encoding="utf-8") as fh:
            fh.write(SCRIPT)
        with open(os.path.join(self.cwd, "work", "act-2.md"), "w", encoding="utf-8") as fh:
            fh.write("INT. CABIN - NIGHT\n\nMore.\n")

    def build(self, inputs, **meta):
        full = dict({"title": "The Third Bell", "author": "Sam Rivers", "language": "en"}, **meta)
        plan = wrist_publish.plan_screenplay(inputs, full, "output", "tb", PUBLISH_DIR)
        wrist_publish.run_commands(plan, self.cwd)

    def typst(self, inputs):
        proc = subprocess.run(["pandoc", "--from", os.path.join(PUBLISH_DIR, "screenplay", "fountain.lua"), *inputs,
                               "-t", "typst", "--lua-filter", os.path.join(PUBLISH_DIR, "screenplay", "screenplay.lua")],
                              cwd=self.cwd, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout

    def test_both_files_are_built(self):
        self.build(["work/act-1.md", "work/act-2.md"], based_on="A short story", draft="First draft",
                   contact="sam@example.com")
        with open(os.path.join(self.cwd, "output/tb.pdf"), "rb") as fh:
            self.assertEqual(fh.read(5), b"%PDF-")
        with zipfile.ZipFile(os.path.join(self.cwd, "output/tb.epub")) as z:
            self.assertEqual(z.namelist()[0], "mimetype")

    def test_the_typst_calls_every_element_and_an_act_marker(self):
        _, markers = wrist_publish.with_act_markers(["work/act-1.md", "work/act-2.md"],
                                                    ["work/act-1.md", "work/act-2.md"], "output", self.cwd)
        typst = self.typst(["output/.wrist-act-1.md", "work/act-1.md", "output/.wrist-act-2.md", "work/act-2.md"])
        for call in ("#sp-act[", "#sp-heading[", "#sp-action[", "#sp-character[", "#sp-parenthetical[",
                     "#sp-dialogue[", "#sp-transition[", "#sp-centered["):
            self.assertIn(call, typst, call)
        self.assertIn("ACT ONE", typst)
        self.assertIn("ACT TWO", typst)
        self.assertNotIn("#sp-act[\nTWO", typst)

    def test_a_forced_page_break_becomes_a_typst_page_break(self):
        with open(os.path.join(self.cwd, "work", "act-2.md"), "w", encoding="utf-8") as fh:
            fh.write("One.\n\n===\n\nTwo.\n")
        self.assertIn("#pagebreak()", self.typst(["work/act-2.md"]))

    def test_review_focus_the_title_page_survives_special_characters(self):
        title = 'A & B #1 — "Q" café'
        self.build(["work/act-1.md"], title=title, author="Zoë & Co", based_on="Based on $5 and @x",
                   contact="a@b.example", draft="Draft #2")
        with zipfile.ZipFile(os.path.join(self.cwd, "output/tb.epub")) as z:
            text = "\n".join(z.read(n).decode("utf-8") for n in z.namelist() if n.endswith(".xhtml"))
        self.assertIn("A &amp; B #1", text)
        self.assertIn("café", text)
        self.assertIn("Zoë &amp; Co", text)
        self.assertIn("Based on $5 and @x", text)          # the title lines pandoc's own title page omits
        self.assertIn("Draft #2", text)
        self.assertIn("a@b.example", text)

    def test_review_focus_the_epub_contents_have_no_stray_entry(self):
        import re
        self.build(["work/act-1.md", "work/act-2.md"])
        with zipfile.ZipFile(os.path.join(self.cwd, "output/tb.epub")) as z:
            nav = z.read("EPUB/nav.xhtml").decode("utf-8")
            pages = [z.read(n).decode("utf-8") for n in z.namelist() if n.startswith("EPUB/text/ch")]
        self.assertEqual(re.findall(r'<a href="[^"]*"[^>]*>([^<]*)</a>', nav), ["Title Page"])
        text = "\n".join(pages)
        for cls in ("scene-heading", "action", "character", "parenthetical", "dialogue", "transition", "centered"):
            self.assertIn(f'class="{cls}"', text, cls)
        self.assertIn('id="script"', text)

    def test_the_epub_stylesheet_hides_the_unlisted_heading_and_styles_the_classes(self):
        with open(os.path.join(PUBLISH_DIR, "screenplay", "screenplay.css"), encoding="utf-8") as fh:
            css = fh.read()
        self.assertIn("#script > h1 { display: none; }", css)
        for cls in ("scene-heading", "character", "dialogue", "parenthetical", "transition", "centered", "act-marker",
                    "title-line"):
            self.assertIn(f"div.{cls}", css)


class TemplateText(unittest.TestCase):
    def read(self, name):
        with open(os.path.join(PUBLISH_DIR, "screenplay", name), encoding="utf-8") as fh:
            return fh.read()

    def test_the_layout_functions_exist_and_the_numbering_is_set_up(self):
        t = self.read("screenplay.typ")
        for fn in ("sp-heading", "sp-action", "sp-character", "sp-parenthetical", "sp-dialogue", "sp-transition",
                   "sp-centered", "sp-act"):
            self.assertIn(f"#let {fn}(body)", t)
        self.assertIn('"Courier Prime", "Courier New", "DejaVu Sans Mono"', t)
        self.assertIn("margin: (left: 1.5in, right: 1in, top: 1in, bottom: 1in)", t)
        self.assertIn("#counter(page).update(0)", t)                  # the script's first page is page 1
        self.assertIn('display("1.")', t)

    def test_character_cues_and_headings_stay_with_what_follows(self):
        t = self.read("screenplay.typ")
        for fn in ("sp-heading", "sp-character", "sp-parenthetical"):
            line = next(l for l in t.split("\n") if l.startswith(f"#let {fn}("))
            self.assertIn("sticky: true", line, fn)


if __name__ == "__main__":
    unittest.main()
