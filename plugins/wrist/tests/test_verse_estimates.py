import unittest

from support import SCRIPTS  # first: it puts the scripts folder on sys.path

import wrist_verse as wv


class Syllables(unittest.TestCase):
    def test_a_word_list(self):
        for word, want in (("the", 1), ("a", 1), ("I", 1), ("stone", 1), ("stones", 1), ("table", 2), ("gentle", 2),
                           ("wished", 1), ("loved", 1), ("wanted", 2), ("boxes", 2), ("faces", 2), ("night", 1),
                           ("water", 2), ("river", 2), ("yellow", 2), ("again", 2), ("beautiful", 3), ("it's", 1)):
            with self.subTest(word):
                self.assertEqual(wv.syllables(word), want)

    def test_a_line_sums_its_words_and_ignores_punctuation(self):
        self.assertEqual(wv.line_syllables("Do not go gentle into that good night,"), 10)
        self.assertEqual(wv.line_syllables("  ...!"), 0)


class RhymeKeys(unittest.TestCase):
    def test_rhyming_pairs_share_a_key(self):
        for a, b in (("light", "night"), ("sky", "high"), ("tree", "free"), ("day", "away"), ("alone", "stone"),
                     ("stone", "bones")):
            with self.subTest((a, b)):
                self.assertEqual(wv.rhyme_key(a), wv.rhyme_key(b))

    def test_other_words_do_not(self):
        for a, b in (("light", "lit"), ("stone", "stun"), ("cat", "cot"), ("day", "dye")):
            with self.subTest((a, b)):
                self.assertNotEqual(wv.rhyme_key(a), wv.rhyme_key(b))


def sk(*stanzas, decl=""):
    return wv.parse_poem("poem {\n" + decl + "\n" + "\n".join(stanzas) + "\n}")


def lines(*specs):
    return "stanza (free, 1, none) {\n" + "\n".join(f"line ({m}, {e}, {t}{x}) {{ }}" for m, e, t, x in specs) + "\n}"


def est(poem, text):
    return [(p.line, p.message) for p in wv.estimates(poem, wv.read_verse(text))]


class Estimates(unittest.TestCase):
    def test_syllables_against_a_foot_meter(self):
        p = sk(lines(("iamb 5", "stop", "x", ""), ("iamb 5", "stop", "x", "")))
        got = est(p, "Do not go gentle into that good night,\nThe brightening rain.\n")
        self.assertEqual(got, [(2, "about 5 syllables, the skeleton asks for 10 to 11 (estimate)")])

    def test_a_feminine_ending_is_allowed(self):
        p = sk(lines(("iamb 5", "stop", "x", "")))
        self.assertEqual(est(p, "To be or not to be, that is the question,\n"), [])

    def test_a_syllable_range_and_free_verse(self):
        p = sk(lines(("syllables 5", "stop", "x", ""), ("syllables 7..9", "stop", "x", ""), ("free", "stop", "x", "")))
        self.assertEqual(est(p, "An old silent pond,\nA frog jumps into the pond,\nSplash.\n"), [])
        got = est(p, "Splash.\nA frog jumps into the pond.\nSplash.\n")
        self.assertEqual(got, [(1, "about 1 syllable, the skeleton asks for 5 (estimate)")])

    def test_stop_and_run_endings(self):
        p = sk(lines(("free", "stop", "x", ""), ("free", "run", "x", "")))
        got = est(p, "an unfinished thought\nbut this one ends.\n")
        self.assertEqual(got, [(1, "a `stop` line should end at a pause, but this one has no end punctuation (estimate)"),
                               (2, "a `run` line should run on, but this one ends a sentence (estimate)")])

    def test_caesura_wants_a_pause_inside_the_line(self):
        p = sk("stanza (free, 1, none) {\nline (free, stop, caesura 2, x) { }\n}")
        self.assertEqual([m for _, m in est(p, "no pause here at all.\n")],
                         ["caesura 2: no pause (comma, dash or colon) inside the line (estimate)"])
        self.assertEqual(est(p, "a pause, inside the line.\n"), [])

    def test_rhyme_groups(self):
        p = sk('stanza (quatrain, 1, A B A B) {\n' + "\n".join(f"line (free, stop, {t}) {{ }}" for t in "ABAB") + "\n}")
        self.assertEqual(est(p, "the light,\nthe day,\nthe stone.\nthe way.\n"),
                         [(3, "'stone' is under rhyme A but may not rhyme with light (estimate)")])
        self.assertEqual(est(p, "the light,\nthe day,\nthe night.\nthe way.\n"), [])

    def test_a_rhyme_word_used_twice(self):
        p = sk('stanza (couplet, 1, A A) {\n' + "\n".join(f"line (free, stop, {t}) {{ }}" for t in "AA") + "\n}")
        got = est(p, "a long light,\nanother light.\n")
        self.assertEqual(got, [(2, "the rhyme word 'light' is used again (lines 1, 2) (estimate)")])

    def test_refrains_and_ends_lines_are_exempt_from_the_repeat_rule(self):
        p = sk('stanza (couplet, 2, A A) {\n' + "\n".join(f"line (free, stop, {t}) {{ }}" for t in "AA") + "\n}",
               decl="refrain R at 1, 3;")
        self.assertEqual(est(p, "one light,\ntwo night.\n\none light,\nfour sight.\n"), [])

    def test_fresh_stanzas_do_not_share_a_rhyme_group(self):
        p = sk('stanza (couplet, 2, fresh A A) {\n' + "\n".join(f"line (free, stop, {t}) {{ }}" for t in "AA") + "\n}")
        self.assertEqual(est(p, "one light,\ntwo night.\n\nthree stone,\nfour bone.\n"), [])

    def test_a_line_count_mismatch_leaves_the_estimates_empty(self):
        p = sk(lines(("iamb 5", "stop", "x", "")))
        self.assertEqual(est(p, "one\ntwo\n"), [])
