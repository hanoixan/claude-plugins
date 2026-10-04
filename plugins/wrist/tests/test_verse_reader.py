import json
import os
import shutil
import subprocess
import unittest

from support import HERE, SKILL  # first: it puts the scripts folder on sys.path

import wrist_verse as wv

with open(os.path.join(HERE, "verse_cases.json"), encoding="utf-8") as fh:
    CASES = json.load(fh)
READER = os.path.join(SKILL, "publish", "poem", "verse.lua")
HAVE_PANDOC = shutil.which("pandoc") is not None


def spaced(text):
    return text.replace(wv.EN, " ")


class PythonReader(unittest.TestCase):
    def test_every_shared_case(self):
        for case in CASES:
            with self.subTest(case["name"]):
                v = wv.read_verse(case["text"])
                self.assertEqual(v.title[1] if v.title else None, case["title"])
                self.assertEqual([[spaced(t) for _, t in st] for st in v.stanzas], case["stanzas"])

    def test_line_numbers_are_physical(self):
        v = wv.read_verse("# T\n\none\ntwo\n\n\nthree\n")
        self.assertEqual(v.title, (1, "T"))
        self.assertEqual([[n for n, _ in st] for st in v.stanzas], [[3, 4], [7]])

    def test_indentation_becomes_en_spaces(self):
        self.assertEqual(wv.read_verse("  a\n").stanzas[0][0][1], wv.EN * 2 + "a")


def inline_text(inlines):
    out = []
    for i in inlines:
        out.append(i["c"] if i["t"] == "Str" else " ")
    return "".join(out)


@unittest.skipUnless(HAVE_PANDOC, "pandoc is not installed")
class LuaReader(unittest.TestCase):
    def read(self, text):
        proc = subprocess.run(["pandoc", "--from", READER, "--to", "json"], input=text, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        title, stanzas = None, []
        for block in json.loads(proc.stdout)["blocks"]:
            cls = block["c"][0][1][0]
            if cls == "title":
                title = inline_text(block["c"][1][0]["c"])
            elif cls == "stanza":
                stanzas.append([spaced(inline_text(line)) for line in block["c"][1][0]["c"]])
        return title, stanzas

    def test_every_shared_case(self):
        for case in CASES:
            with self.subTest(case["name"]):
                self.assertEqual(self.read(case["text"]), (case["title"], case["stanzas"]))

    def test_special_characters_stay_literal_in_the_json(self):
        title, stanzas = self.read("a $ # * _ \\ < > & ` [x]\n")
        self.assertEqual(stanzas, [["a $ # * _ \\ < > & ` [x]"]])
