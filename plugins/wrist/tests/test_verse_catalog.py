import os
import unittest

from support import SKILL  # first: it puts the scripts folder on sys.path

import wrist_verse as wv

FORMS = os.path.join(SKILL, "profiles", "poem", "forms")

# Written out by hand from the definition of each form, not from the catalog files.
SHAPE = {   # name: (lines, canonical rhyme scheme, refrains, stanza sizes)
    "villanelle": (19, "ABA" * 5 + "ABAA", [(1, 6, 12, 18), (3, 9, 15, 19)], [3] * 5 + [4]),
    "sonnet-shakespearean": (14, "ABABCDCDEFEFGG", [], [4, 4, 4, 2]),
    "sonnet-petrarchan": (14, "ABBAABBACDECDE", [], [8, 6]),
    "sestina": (39, "x" * 39, [], [6] * 6 + [3]),
    "pantoum": (16, "x" * 16, [(1, 16), (2, 5), (3, 14), (4, 7), (6, 9), (8, 11), (10, 13), (12, 15)], [4] * 4),
    "haiku": (3, "xxx", [], [3]),
    "tanka": (5, "xxxxx", [], [5]),
    "limerick": (5, "AABBA", [], [5]),
    "triolet": (8, "ABAAABAB", [(1, 4, 7), (2, 8)], [8]),
}
OPEN = ("ballad", "couplets", "blank-verse", "free-verse")
SESTINA_ENDS = [int(c) - 1 for c in "123456" "615243" "364125" "532614" "451362" "246531"] + [4, 2, 0]


def catalog(name):
    return wv.load_catalog(name, FORMS)


class CatalogFiles(unittest.TestCase):
    def test_the_catalog_lists_every_form(self):
        self.assertEqual(wv.list_catalog(FORMS), sorted(list(SHAPE) + list(OPEN)))

    def test_an_unknown_form_is_none(self):
        self.assertIsNone(wv.load_catalog("sapphic", FORMS))
        self.assertIsNone(wv.load_catalog("../villanelle", FORMS))

    def test_every_form_parses_names_itself_and_passes_the_rules(self):
        for name in wv.list_catalog(FORMS):
            with self.subTest(name):
                poem = catalog(name)
                self.assertEqual(poem.named, name)
                self.assertEqual(wv.skeleton_problems(poem, concrete=False), [])
                self.assertLessEqual(sum(1 for s in poem.stanzas if s.count.lo != s.count.hi), 1)

    def test_each_fixed_form_has_its_lines_scheme_refrains_and_stanzas(self):
        for name, (lines, scheme, refrains, sizes) in SHAPE.items():
            with self.subTest(name):
                poem = catalog(name)
                xs = wv.expand(poem)
                self.assertEqual(len(xs), lines)
                self.assertEqual("".join(wv.canonical_tags(xs)), scheme)
                self.assertEqual(sorted(tuple(r.positions) for r in poem.refrains), sorted(refrains))
                self.assertEqual([sum(1 for x in xs if x.stanza_no == n) for n in range(1, xs[-1].stanza_no + 1)], sizes)

    def test_the_sestina_rotates_its_end_words(self):
        xs = wv.expand(catalog("sestina"))
        self.assertEqual([x.line.ends[1] for x in xs], SESTINA_ENDS)

    def test_syllable_forms(self):
        def meters(name):
            return [(x.line.meter.lo, x.line.meter.hi) for x in wv.expand(catalog(name))]
        self.assertEqual(meters("haiku"), [(5, 5), (7, 7), (5, 5)])
        self.assertEqual(meters("tanka"), [(5, 5), (7, 7), (5, 5), (7, 7), (7, 7)])
        self.assertEqual(meters("limerick"), [(8, 9), (8, 9), (5, 6), (5, 6), (8, 9)])

    def test_the_open_forms_repeat_one_stanza(self):
        for name, count in (("ballad", wv.Count(2, 40)), ("couplets", wv.Count(1, None)), ("blank-verse", wv.Count(1, None)),
                            ("free-verse", wv.Count(1, None))):
            with self.subTest(name):
                self.assertEqual(catalog(name).stanzas[0].count, count)

    def test_the_sonnets_and_open_free_forms_may_move_their_breaks(self):
        for name in ("sonnet-shakespearean", "sonnet-petrarchan", "blank-verse", "free-verse"):
            self.assertTrue(catalog(name).flexible, name)
        for name in ("villanelle", "sestina", "pantoum", "triolet", "haiku", "ballad"):
            self.assertFalse(catalog(name).flexible, name)


def compare(skeleton, name):
    return [(p.line, p.message) for p in wv.catalog_problems(wv.parse_poem(skeleton), catalog(name), name)]


class Comparison(unittest.TestCase):
    def test_a_form_matches_itself(self):
        for name in wv.list_catalog(FORMS):
            with self.subTest(name):
                with open(os.path.join(FORMS, name + ".psg"), encoding="utf-8") as fh:
                    text = fh.read()
                poem = wv.parse_poem(text)
                self.assertEqual(wv.catalog_problems(poem, catalog(name), name), [])

    def read(self, name):
        with open(os.path.join(FORMS, name + ".psg"), encoding="utf-8") as fh:
            return fh.read()

    def test_other_letters_are_the_same_scheme(self):
        text = self.read("sonnet-shakespearean").replace("A", "Q").replace("B", "R")
        self.assertEqual(compare(text, "sonnet-shakespearean"), [])

    def test_a_different_rhyme_scheme_is_named(self):
        text = self.read("sonnet-shakespearean").replace("stanza (quatrain, 1, E F E F)", "stanza (quatrain, 1, E E F F)")
        text = text.replace("line (iamb 5, stop, F) { }\n    line (iamb 5, stop, E) { }\n    line (iamb 5, stop, F)",
                            "line (iamb 5, stop, E) { }\n    line (iamb 5, stop, F) { }\n    line (iamb 5, stop, F)")
        got = compare(text, "sonnet-shakespearean")
        self.assertEqual(len(got), 1)
        self.assertIn("named form sonnet-shakespearean: the rhyme scheme differs at line 10: sonnet-shakespearean has F, "
                      "this skeleton has E", got[0][1])

    def test_a_wrong_line_count(self):
        text = self.read("haiku").replace('line (syllables 5, stop, x) { }\n  }', 'line (syllables 5, stop, x) { }\n    line (syllables 5, stop, x) { }\n  }').replace("tercet", "free")
        self.assertEqual([m for _, m in compare(text, "haiku")], ["named form haiku: haiku has 3 lines, this skeleton has 4"])

    def test_missing_refrains(self):
        text = self.read("villanelle").replace("refrain R2 at 3, 9, 15, 19;\n", "")
        got = compare(text, "villanelle")
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0][1], "named form villanelle: the refrains differ: villanelle repeats lines 1,6,12,18; 3,9,15,19, "
                                    "this skeleton repeats 1,6,12,18")

    def test_a_wrong_meter(self):
        text = self.read("haiku").replace("syllables 7", "syllables 6")
        got = compare(text, "haiku")
        self.assertEqual([m for _, m in got], ["named form haiku: the meter differs at line 2: haiku has 7 syllables, "
                                               "this skeleton has 6 syllables"])

    def test_a_flexible_form_accepts_other_breaks(self):
        text = self.read("sonnet-shakespearean")
        flat = ("poem {\n  named \"sonnet-shakespearean\";\n  stanza (free, 1, A B A B C D C D E F E F G G) {\n" +
                "".join(f"    line (iamb 5, stop, {t}) {{ }}\n" for t in "ABABCDCDEFEFGG") + "  }\n}\n")
        self.assertEqual(compare(flat, "sonnet-shakespearean"), [])

    def test_a_fixed_form_rejects_other_breaks(self):
        lines = "".join(f"    line (syllables {n}, stop, x) {{ }}\n" for n in (5, 7, 5))
        one_each = "poem {\n  named \"haiku\";\n" + "".join(f"  stanza (free, 1, none) {{\n{l}  }}\n" for l in lines.splitlines(True)) + "}\n"
        got = compare(one_each, "haiku")
        self.assertEqual([m for _, m in got], ["named form haiku: the stanzas should be 3 lines long, this skeleton has 1,1,1"])

    def test_villanelle_breaks_are_fixed(self):
        text = self.read("villanelle")
        tercets = text[text.index("  stanza (tercet"):text.index("  stanza (quatrain")]
        lines = "".join(l for l in tercets.splitlines(True) if "line (" in l) * 5
        quatrain = "".join(l for l in text[text.index("  stanza (quatrain"):].splitlines(True) if "line (" in l)
        one = (text[:text.index("  stanza (tercet")] + "  stanza (free, 1, A B A A B A A B A A B A A B A A B A A) {\n"
               + lines + quatrain + "  }\n}\n")
        got = compare(one, "villanelle")
        self.assertEqual([m for _, m in got], ["named form villanelle: the stanzas should be 3,3,3,3,3,4 lines long, "
                                               "this skeleton has 19"])

    def test_sestina_end_word_pattern(self):
        text = self.read("sestina").replace("ends @end_words[5]", "ends @end_words[4]", 1)
        got = compare(text, "sestina")
        self.assertEqual(len(got), 1)
        self.assertIn("the `ends` pattern differs at line 6: sestina has end word 5, this skeleton has end word 4", got[0][1])

    def test_a_repeating_form_resolves_its_count_from_the_lines(self):
        ballad = "poem {\n  named \"ballad\";\n  stanza (quatrain, 3, fresh x A x A) {\n" + "".join(
            f"    line (iamb {m}, stop, {t}) {{ }}\n" for m, t in ((4, "x"), (3, "A"), (4, "x"), (3, "A"))) + "  }\n}\n"
        self.assertEqual(compare(ballad, "ballad"), [])
        too_few = ballad.replace("quatrain, 3", "quatrain, 1")
        self.assertEqual([m for _, m in compare(too_few, "ballad")],
                         ["named form ballad: ballad repeats its stanza 2..40 times (4 lines each); this skeleton's 4 lines do not fit"])
        not_rhymed_fresh = ballad.replace("fresh x A", "x A")
        self.assertEqual(len(compare(not_rhymed_fresh, "ballad")), 1)

    def test_open_forms_accept_any_length(self):
        for n in (1, 7, 40):
            body = "".join("    line (iamb 5, stop, x) { }\n" for _ in range(n))
            skeleton = f"poem {{\n  named \"blank-verse\";\n  stanza (free, 1, none) {{\n{body}  }}\n}}\n"
            self.assertEqual(compare(skeleton, "blank-verse"), [], n)
