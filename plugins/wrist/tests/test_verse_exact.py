import unittest

from support import SCRIPTS  # first: it puts the scripts folder on sys.path

import wrist_verse as wv


def sk(*parts):
    return wv.parse_poem("poem {\n" + "\n".join(parts) + "\n}")


def st(count, lines, shape="free", rhyme="none"):
    body = "\n".join(f"line (free, stop, {t}{', ends @w[%d]' % e if e is not None else ''}) {{ }}" for t, e in lines)
    return f"stanza ({shape}, {count}, {rhyme}) {{\n{body}\n}}"


def errors(poem, text, titled=False, title="T"):
    return [(l, m) for s, l, m in wv.poem_problems(poem, wv.read_verse(text), titled, title)]


class Normal(unittest.TestCase):
    def test_comparison_ignores_case_space_punctuation_and_curly_quotes(self):
        self.assertEqual(wv.normal("  Do not  GO gentle, "), wv.normal("do not go gentle"))
        self.assertEqual(wv.normal("“No,” she said."), 'no," she said')
        self.assertEqual(wv.normal("    indented!"), "indented")
        self.assertNotEqual(wv.normal("do not go"), wv.normal("do not stay"))

    def test_words(self):
        self.assertEqual(wv.words("The stone's cold, still."), ["the", "stone's", "cold", "still"])


class Stanzas(unittest.TestCase):
    P = sk(st(1, [("x", None)] * 2), st(1, [("x", None)] * 3))

    def test_a_matching_poem_has_no_errors(self):
        self.assertEqual(errors(self.P, "a\nb\n\nc\nd\ne\n"), [])

    def test_the_stanza_count(self):
        self.assertEqual(errors(self.P, "a\nb\nc\nd\ne\n"), [(1, "the skeleton has 2 stanzas, the poem has 1"),
                                                           (1, "stanza 1 has 5 lines, the skeleton says 2")])

    def test_a_stanza_with_the_wrong_number_of_lines(self):
        got = errors(self.P, "a\nb\nc\n\nd\ne\n")
        self.assertEqual(got[0], (1, "stanza 1 has 3 lines, the skeleton says 2"))
        self.assertEqual(got[1], (5, "stanza 2 has 2 lines, the skeleton says 3"))

    def test_extra_blank_lines_between_stanzas_do_not_matter(self):
        self.assertEqual(errors(self.P, "\n\na\nb\n\n\n\nc\nd\ne\n"), [])


class Titles(unittest.TestCase):
    P = sk(st(1, [("x", None)]))

    def test_a_title_when_untitled(self):
        self.assertEqual(errors(self.P, "# Name\n\na\n"), [(1, "the poem has a title line but PREMISE.md says `titled: no`")])

    def test_no_title_when_titled(self):
        self.assertEqual(errors(self.P, "a\n", titled=True), [(1, "PREMISE.md says `titled: yes` but the poem has no `# Title` line first")])

    def test_the_title_must_match_the_premise(self):
        self.assertEqual(errors(self.P, "# Other\n\na\n", titled=True, title="T"),
                         [(1, "the title line 'Other' differs from the premise title 'T'")])
        self.assertEqual(errors(self.P, "# T\n\na\n", titled=True, title="T"), [])


class Refrains(unittest.TestCase):
    P = sk("refrain R at 1, 3;", st(1, [("x", None)] * 4))

    def test_a_repeated_refrain_passes_despite_case_and_punctuation(self):
        self.assertEqual(errors(self.P, "Do not go gentle,\nb\ndo not go gentle\nd\n"), [])

    def test_a_changed_refrain_is_named_with_its_source(self):
        got = errors(self.P, "Do not go gentle\nb\nDo not stay gentle\nd\n")
        self.assertEqual(got, [(3, "R8: line 3 must repeat line 1 (refrain R) word for word: 'Do not go gentle'")])

    def test_a_wrong_line_count_stops_the_line_checks(self):
        got = errors(self.P, "x\ny\n")
        self.assertEqual(got, [(1, "stanza 1 has 2 lines, the skeleton says 4"),
                               (1, "the skeleton has 4 lines, the poem has 2")])


class Ends(unittest.TestCase):
    P = sk('let w = ["shadow", "moon"];', st(1, [("x", 0), ("x", 1), ("x", 0)]))

    def test_lines_must_end_on_their_word(self):
        self.assertEqual(errors(self.P, "a long shadow.\nthe moon\nand a Shadow,\n"), [])

    def test_a_line_that_does_not(self):
        got = errors(self.P, "a long shadow\nthe sun\nand the dark\n")
        self.assertEqual(got, [(2, "R12: line 2 must end with 'moon'"), (3, "R12: line 3 must end with 'shadow'")])

    def test_a_multi_word_element_must_end_the_line(self):
        p = sk('let w = ["the moon"];', st(1, [("x", 0)]))
        self.assertEqual(errors(p, "over the moon\n"), [])
        self.assertEqual(errors(p, "a moon\n"), [(1, "R12: line 1 must end with 'the moon'")])
