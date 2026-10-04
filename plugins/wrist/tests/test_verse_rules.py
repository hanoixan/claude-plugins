import unittest

from support import SCRIPTS  # first: it puts the scripts folder on sys.path

import wrist_verse as wv


def poem(*decls_and_stanzas):
    return wv.parse_poem("poem {\n" + "\n".join(decls_and_stanzas) + "\n}")


def stanza(shape, count, rhyme, lines, role=""):
    return f"stanza ({shape}, {count}, {rhyme}{', ' + role if role else ''}) {{\n" + "\n".join(lines) + "\n}"


def ln(tag="x", meter="free", ending="stop", extra="", units=""):
    return f"line ({meter}, {ending}, {tag}{extra}) {{ {units} }}"


def messages(p, concrete=True):
    return [m for _, _, m in wv.skeleton_problems(p, concrete)]


class Expansion(unittest.TestCase):
    def test_counts_expand_and_positions_run_on(self):
        p = poem(stanza("couplet", 3, "A B", [ln("A"), ln("B")]), stanza("tercet", 1, "none", [ln(), ln(), ln()]))
        xs = wv.expand(p)
        self.assertEqual(len(xs), 9)
        self.assertEqual([x.position for x in xs], list(range(1, 10)))
        self.assertEqual([x.stanza_no for x in xs], [1, 1, 2, 2, 3, 3, 4, 4, 4])
        self.assertEqual([x.tag for x in xs], ["A", "B"] * 3 + ["x"] * 3)

    def test_fresh_renames_the_tags_per_repeat_and_leaves_x(self):
        p = poem(stanza("couplet", 2, "fresh A x", [ln("A"), ln("x")]))
        self.assertEqual([x.tag for x in wv.expand(p)], ["A.1", "x", "A.2", "x"])

    def test_a_range_uses_its_lower_bound_unless_told(self):
        p = poem(stanza("couplet", "2..9", "none", [ln(), ln()]))
        self.assertEqual(len(wv.expand(p)), 4)
        self.assertEqual(len(wv.expand(p, {0: 5})), 10)

    def test_refrain_positions(self):
        p = poem("refrain R at 1, 3;", stanza("couplet", 2, "none", [ln(), ln()]))
        self.assertEqual({k: v.name for k, v in wv.refrain_positions(p).items()}, {1: "R", 3: "R"})


class Rules(unittest.TestCase):
    def test_a_clean_skeleton_has_no_problems(self):
        p = poem(stanza("couplet", 1, "A A", [ln("A"), ln("A")]))
        self.assertEqual(wv.skeleton_problems(p), [])

    def test_r0_unknown_reference_and_bad_index(self):
        p = poem('let w = ["a", "b"]; let s = "one";',
                 stanza("couplet", 1, "none", [ln(units='image["see @missing"]'),
                                               ln(units='image["@w[5] and @s[0] and @w[x]"]')]))
        got = messages(p)
        self.assertIn("R0: the hint refers to @missing, which no `let` declares", got)
        self.assertEqual(sum("is not an item of the list" in m for m in got), 3)

    def test_r0_dollar_n_needs_a_repeated_stanza(self):
        once = poem('let w = ["a"];', stanza("couplet", 1, "none", [ln(units='image["@w[$n]"]'), ln()]))
        self.assertIn("R0: $n is only allowed in a stanza repeated more than once", messages(once))
        bare = poem(stanza("couplet", 1, "none", [ln(units='image["round $n"]'), ln()]))
        self.assertIn("R0: $n is only allowed in a stanza repeated more than once", messages(bare))
        repeated = poem('let w = ["a"];', stanza("couplet", 2, "none", [ln(units='image["round $n at @w[$n]"]'), ln()]))
        self.assertEqual(messages(repeated), [])

    def test_r0_ends_needs_a_list_and_an_index_in_range(self):
        p = poem('let w = ["a", "b"]; let s = "x";',
                 stanza("tercet", 1, "none", [ln(extra=", ends @w[2]"), ln(extra=", ends @s[0]"), ln(extra=", ends @nope[0]")]))
        got = messages(p)
        self.assertEqual(sum("R0: `ends" in m for m in got), 3)
        self.assertTrue(any("past the end of the list" in m for m in got))

    def test_r1_scheme_length_and_agreement(self):
        p = poem(stanza("couplet", 1, "A B A", [ln("A"), ln("B")]))
        self.assertIn("R1: the rhyme scheme has 3 tags for 2 lines", messages(p))
        q = poem(stanza("couplet", 1, "A B", [ln("A"), ln("A")]))
        self.assertIn("R1: the scheme says B but this line is tagged A", messages(q))
        none = poem(stanza("couplet", 1, "none", [ln("A"), ln()]))
        self.assertIn("R1: the stanza says `none` but this line is tagged A", messages(none))

    def test_r2_shape_line_counts(self):
        p = poem(stanza("tercet", 1, "none", [ln(), ln()]))
        self.assertIn("R2: a tercet has 3 lines, this stanza has 2", messages(p))
        free = poem(stanza("free", 1, "none", [ln()]))
        self.assertEqual(wv.skeleton_problems(free), [])

    def test_r8_refrain_positions_and_agreement(self):
        base = stanza("couplet", 2, "A B", [ln("A"), ln("B")])
        self.assertIn("R8: refrain R: line 9 is outside the poem (it has 4 lines)", messages(poem("refrain R at 1, 9;", base)))
        self.assertIn("R8: refrain R: line numbers must rise and not repeat", messages(poem("refrain R at 3, 1;", base)))
        self.assertIn("R8: line 3 is already in refrain Q", messages(poem("refrain Q at 1, 3; refrain R at 3, 4;", base)))
        self.assertIn("R8: line 2 repeats line 1 (refrain R) but its meter, ending or tag differs",
                      messages(poem("refrain R at 1, 2;", base)))

    def test_r11_a_realized_skeleton_has_exact_counts(self):
        p = poem(stanza("couplet", "2..*", "none", [ln(), ln()]))
        self.assertIn("R11: the count must be exact here (found 2..*); choose a number", messages(p))
        self.assertEqual(messages(p, concrete=False), [])

    def test_problems_carry_line_numbers_in_order(self):
        p = poem(stanza("tercet", 1, "none", [ln(), ln()]))
        self.assertEqual([(s, l) for s, l, _ in wv.skeleton_problems(p)], [("error", 2)])


class StrictRoles(unittest.TestCase):
    def good(self):
        return poem("strict roles;",
                    stanza("quatrain", 1, "none", [ln(units='image["a"]'), ln(units='image["b"]'), ln(units='action["c"]'),
                                                   ln(units='statement["d"]')], "setup"),
                    stanza("quatrain", 1, "none", [ln(units='pivot["but"]'), ln(units='image["e"]'), ln(units='image["f"]'),
                                                   ln(units='statement["g"]')], "turn"))

    def test_a_conforming_poem_passes(self):
        self.assertEqual(wv.skeleton_problems(self.good()), [])

    def test_roles_are_not_checked_unless_strict(self):
        p = poem(stanza("couplet", 1, "none", [ln(units='statement["only"]'), ln()], "turn"))
        self.assertEqual(wv.skeleton_problems(p), [])

    def test_r3_a_role_pattern_must_match_exactly(self):
        p = poem("strict roles;", stanza("couplet", 1, "none", [ln(units='image["a"]'), ln(units='statement["b"]')], "turn"))
        got = messages(p)
        self.assertTrue(any(m.startswith("R3: a turn stanza reads pivot (image | question)") for m in got), got)

    def test_r3_every_stanza_needs_a_role_when_strict(self):
        p = poem("strict roles;", stanza("couplet", 1, "none", [ln(), ln()]))
        self.assertIn("R3: under `strict roles;` every stanza needs a role", messages(p))

    def test_r4_exactly_one_turn(self):
        p = poem("strict roles;", stanza("couplet", 1, "none", [ln(units='image["a"]'), ln(units='statement["b"]')], "resolve"))
        self.assertIn("R4: exactly one stanza must be the turn (found 0)", messages(p))

    def test_r5_a_statement_needs_an_earlier_image_in_its_stanza(self):
        p = poem("strict roles;", stanza("couplet", 1, "none", [ln(units='action["a"]'), ln(units='statement["b"]')], "develop"))
        self.assertIn("R5: a statement needs an image before it in its own stanza", messages(p))

    def test_the_poem_must_end_on_a_statement_when_strict(self):
        p = poem("strict roles;", stanza("tercet", 1, "none", [ln(units='pivot["but"]'), ln(units='image["a"]'),
                                                              ln(units='image["b"]')], "develop"))
        self.assertIn("R3: under `strict roles;` the poem ends on a statement", messages(p))
