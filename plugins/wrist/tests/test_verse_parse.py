import unittest

from support import SCRIPTS  # first: it puts the scripts folder on sys.path

import wrist_verse as wv

MINI = '''poem {
  stanza (couplet, 1, A A, setup) {
    line (iamb 5, stop, A) { image["a stone"]; action["held"] }
    line (iamb 5, stop, A) { statement["it is cold"] }
  }
}
'''


class Tokens(unittest.TestCase):
    def test_tokens_carry_line_and_column(self):
        toks = wv.tokenize('poem {\n  "a\\"b" 5..*\n}')
        self.assertEqual([(k, v) for k, v, _, _ in toks],
                         [("ident", "poem"), ("punct", "{"), ("str", 'a"b'), ("int", "5"), ("dots", ".."),
                          ("punct", "*"), ("punct", "}"), ("end", "")])
        self.assertEqual(toks[2][2:], (2, 3))
        self.assertEqual(toks[-1][2:], (3, 2))

    def test_comments_are_skipped_and_keep_line_numbers(self):
        toks = wv.tokenize("(* one\ntwo *) poem")
        self.assertEqual(toks[0][1:], ("poem", 2, 8))

    def test_an_unexpected_character_names_its_place(self):
        with self.assertRaises(wv.ParseError) as cm:
            wv.tokenize("poem {\n  $ }")
        self.assertEqual((cm.exception.line, cm.exception.col), (2, 3))
        self.assertIn("unexpected the character '$'", str(cm.exception))

    def test_an_unterminated_string_is_named(self):
        with self.assertRaises(wv.ParseError) as cm:
            wv.tokenize('poem { title "abc')
        self.assertIn("unterminated string", str(cm.exception))


class Parsing(unittest.TestCase):
    def test_a_minimal_poem(self):
        poem = wv.parse_poem(MINI)
        self.assertEqual(len(poem.stanzas), 1)
        st = poem.stanzas[0]
        self.assertEqual((st.shape, st.count, st.fresh, st.rhyme, st.role), ("couplet", wv.Count(1, 1), False, ["A", "A"], "setup"))
        self.assertEqual(st.lines[0].meter, wv.Meter("foot", "iamb", 5, None, None, None))
        self.assertEqual([u.kind for u in st.lines[0].units], ["image", "action"])
        self.assertEqual(st.lines[0].units[0].hint, "a stone")
        self.assertEqual((st.lines[0].ending, st.lines[0].tag, st.lines[0].ends, st.lines[0].caesura), ("stop", "A", None, None))

    def test_declarations(self):
        poem = wv.parse_poem('''poem {
          named "villanelle"; title "T"; strict roles; breaks flexible;
          let w = ["a", "b"]; let one = "x";
          refrain R1 at 1, 6, 12;
          stanza (couplet, 1, none) { line (free, run, x) {} line (free, stop, x) {} }
        }''')
        self.assertEqual((poem.named, poem.title, poem.strict, poem.flexible), ("villanelle", "T", True, True))
        self.assertEqual(poem.lets, {"w": ["a", "b"], "one": "x"})
        self.assertEqual(poem.refrains, [wv.Refrain("R1", [1, 6, 12], poem.refrains[0].line)])
        self.assertIsNone(poem.stanzas[0].rhyme)

    def test_counts_meters_endings_and_ends(self):
        poem = wv.parse_poem('''poem {
          stanza (tercet, 2..5, fresh A B A) {
            line (syllables 5, stop, A, ends @w[0]) { }
            line (syllables 7..9, run, caesura 2, B) { }
            line (stress "1010", stop, A) { }
          }
          stanza (free, 3..*, none) { line (trochee 4, stop, x) { } }
        }''')
        a, b = poem.stanzas
        self.assertEqual((a.count, a.fresh, a.rhyme), (wv.Count(2, 5), True, ["A", "B", "A"]))
        self.assertEqual(a.lines[0].meter, wv.Meter("syllables", None, None, 5, 5, None))
        self.assertEqual(a.lines[0].ends, ("w", 0))
        self.assertEqual(a.lines[1].meter, wv.Meter("syllables", None, None, 7, 9, None))
        self.assertEqual(a.lines[1].caesura, 2)
        self.assertEqual(a.lines[2].meter.pattern, "1010")
        self.assertEqual(b.count, wv.Count(3, None))

    def test_units_may_be_separated_by_semicolons_or_not(self):
        poem = wv.parse_poem('poem { stanza (couplet, 1, none) { line (free, stop, x) { image["a"] action["b"]; pivot["c"]; } '
                             'line (free, stop, x) { } } }')
        self.assertEqual([u.kind for u in poem.stanzas[0].lines[0].units], ["image", "action", "pivot"])


class ParseErrors(unittest.TestCase):
    def fails(self, text, fragment, line=None):
        with self.assertRaises(wv.ParseError) as cm:
            wv.parse_poem(text)
        self.assertIn(fragment, str(cm.exception))
        if line is not None:
            self.assertEqual(cm.exception.line, line)

    def test_text_that_is_not_a_poem(self):
        self.fails("stanza", "expected 'poem', found 'stanza'", 1)

    def test_a_poem_needs_a_stanza(self):
        self.fails("poem { }", "needs at least one stanza")

    def test_an_unknown_shape_lists_the_shapes(self):
        self.fails("poem {\n stanza (triplet, 1, none) { } }", "expected a shape (couplet, tercet", 2)

    def test_an_unknown_foot(self):
        self.fails("poem { stanza (couplet, 1, none) { line (iambic 5, stop, x) { } } }", "expected a meter")

    def test_a_bad_tag(self):
        self.fails("poem { stanza (couplet, 1, a A) { } }", "expected a rhyme tag (A to Z, or x")

    def test_a_stress_pattern_uses_ones_and_zeros(self):
        self.fails('poem { stanza (couplet, 1, none) { line (stress "/10", stop, x) { } } }', "only 1 (stressed) and 0")

    def test_a_missing_semicolon(self):
        self.fails('poem { named "x" stanza', "expected ';', found 'stanza'")

    def test_a_refrain_needs_two_positions(self):
        self.fails("poem { refrain R at 3; }", "refrain R needs at least two line numbers", 1)

    def test_a_let_declared_twice(self):
        self.fails('poem { let a = "x"; let a = "y"; }', "'a' is declared twice")

    def test_a_unit_kind_is_checked(self):
        self.fails('poem { stanza (couplet, 1, none) { line (free, stop, x) { simile["a"] } } }', "expected a unit kind")

    def test_text_after_the_poem(self):
        self.fails(MINI + "poem", "expected the end of the text")
