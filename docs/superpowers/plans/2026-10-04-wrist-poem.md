# wrist poem profile (cycle 4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the `poem` profile to wrist: a poem planned as a skeleton in the fixed PSGv2.1 grammar, checked by a `verse` command, written as plain verse, and published as a poem-layout PDF and EPUB.

**Architecture:** A new standard-library module `wrist_verse.py` holds everything about verse: a recursive-descent parser for the skeleton grammar, expansion, the well-formedness rules, the verse reader, the exact and advisory checks of a poem against its skeleton, and the catalog of forms (`profiles/poem/forms/*.psg`). The engine gains a generic profile setting `form` and a `verse` command; `gate publishing` adds the exact checks. Publishing gets a `poem` style: a custom Lua reader (`verse.lua`), a Typst filter and template, and a stylesheet. The reader (Lua) and the Python reader implement the same rules and are tested against one shared case file. Every layout piece and every module in this plan was prototyped and run before the plan was written; the code below is that code.

**Tech Stack:** Python 3.10 standard library (scripts and `unittest`); pandoc 3.12 (custom Lua reader, Lua filter) and typst 0.15 for the real builds (installed on this machine; real-build tests skip when absent).

**Spec:** `docs/superpowers/specs/2026-10-04-wrist-poem-design.md` (builds on the foundation, novel and screenplay specs)

## Global Constraints

- Scripts and tests use only the Python standard library; profiles are JSON; the catalog forms are text in the PSGv2.1 grammar.
- The checker stays generic: no poem vocabulary in `wrist_check.py` or `wrist_profile.py` beyond the profile `form` setting (`structure` and `poem` paths) and the `verse` command that uses it. Verse knowledge lives in `wrist_verse.py`, `wrist_publish.py` and `publish/poem/`.
- The short story, novel and screenplay profiles, examples and all their tests keep passing unchanged (388 tests before this plan). A profile with no `form` key behaves exactly as before.
- Stand-ins hold notes, never final text. `plugins/skel/` is not modified.
- Exact things are errors (parse errors, rules R0 to R12, stand-in and catalog disagreement, stanza and line counts, refrains word for word, `ends` words, the title line). Syllables, rhyme, `stop`/`run` endings and caesura are advisory estimates, always labelled `(estimate)`, and never block a gate.
- The Lua reader and the Python reader follow the rules in `tests/verse_cases.json`; changing a rule means changing that file first.
- The estimates are English only and rough by design. Do not tune them to a taste; a change needs a failing word-list or rhyme-pair test first.
- A poem's title is printed only when `PREMISE.md` says `titled: yes`; the front matter `title:` is always required.
- Fonts: Libertinus Serif, then DejaVu Serif (bundled with typst). The test suite has no PDF reader; layout is verified by rendering pages (a scratch virtualenv with `pymupdf`) and looking.

## Review Focus

Inputs the spec implies that no obvious test would reach. Each has a test in the task that owns the code.

1. A refrain line changed only by case, spacing, curly quotes or end punctuation passes; one changed word fails, and the message names the source line. Task 4.
2. A skeleton with a refrain position past the end of the poem (or an `ends` index past its list) must not crash the poem check; the poem is reported as not checked. Task 9 (this crashed in the prototype).
3. A title, epigraph, dedication or verse line holding `&`, `#`, `@`, `$`, quotes, accents, `*`, `_`, a backslash or brackets reaches the PDF and the EPUB intact. Tasks 3, 8, 9.
4. The EPUB has one contents entry and no stray first section (a dedication before the heading made one in the prototype); an untitled poem's heading is hidden but present. Task 9.
5. `titled` against the poem's first line, in both directions, and a printed title that differs from the premise title. Tasks 4 and 9.
6. `verse` while the poem file is missing still checks the skeleton, and a missing skeleton ends the run cleanly. Task 9.
7. A ballad (`fresh` tags, a repeated stanza of unknown count) resolves its repeat count from the line total, and fits or fails with a clear message. Task 6.

---

## File structure

```text
plugins/wrist/
  skills/wrist/
    scripts/wrist_verse.py        new: parser, rules, reader, checks, estimates, catalog
    scripts/wrist_profile.py      edited: the `form` setting
    scripts/wrist_publish.py      edited: the `poem` style and plan_poem
    scripts/wrist_check.py        edited: the `verse` command, the gate, the poem publish branch
    profiles/poem/                profile.json, questions.md, forms.md, quality.md, lint.json,
                                  forms/*.psg (13 catalog skeletons)
    publish/poem/                 verse.lua, poem.lua, poem.typ, poem.css
    assets/templates/poem/        PREMISE.md, structure.wrist.md, poem.wrist.md, skeleton.md
    assets/examples/counting/     a complete villanelle
    references/psg.md, verse.md (new); grammar.md, publishing.md, SKILL.md (edited)
  tests/ test_verse_parse.py, test_verse_rules.py, test_verse_reader.py, test_verse_exact.py,
         test_verse_estimates.py, test_verse_catalog.py, test_poem_profile.py, test_poem_publish.py,
         test_poem.py, verse_cases.json (new); support.py, test_profile.py, test_docs.py (edited)
```

All paths below are relative to the repository root. Run every command from it. The branch is `wrist-poem`.

---


### Task 1: The skeleton parser

**Files:**
- Create: `plugins/wrist/skills/wrist/scripts/wrist_verse.py` (part 1), `plugins/wrist/tests/test_verse_parse.py`

**Interfaces:**
- Produces in `wrist_verse`: constants `SHAPES` (shape name to line count, `free` is `None`), `ROLES`, `FEET` (foot to syllables per foot), `KINDS`, `ENDINGS`; namedtuples `Problem(severity, line, message)`, `Meter(kind, foot, n, lo, hi, pattern)` with `kind` one of `foot syllables free stress`, `Unit(kind, hint, line)`, `Refrain(name, positions, line)`, `Count(lo, hi)` (`hi` is `None` for `N..*`), `Line(meter, ending, caesura, tag, ends, units, line)` (`ends` is `(list name, index)` or `None`), `Stanza(shape, count, fresh, rhyme, role, lines, line)` (`rhyme` is the tag list or `None` for `none`), `Poem(named, title, strict, flexible, lets, refrains, stanzas)` (`lets` maps a name to a string or a list of strings); `ParseError(line, col, message)` (an `Exception`; `str()` is `line:col: message`); `tokenize(text)`; `parse_poem(text) -> Poem`.

- [ ] **Step 1: Write the failing tests**

Create `plugins/wrist/tests/test_verse_parse.py`:

````python
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
````

- [ ] **Step 2: Run them to see them fail**

Run: `python3 -m unittest discover -s plugins/wrist/tests -p "test_verse_parse.py" -q 2>&1 | tail -4`
Expected: an error, `ModuleNotFoundError: No module named 'wrist_verse'`.

- [ ] **Step 3: Write the parser**

Create `plugins/wrist/skills/wrist/scripts/wrist_verse.py`:

````python
#!/usr/bin/env python3
"""wrist_verse.py: PSGv2.1 poem skeletons and the checks for a poem written into one.

A skeleton (structure.md) is a document in the poem grammar described in references/psg.md. This module
parses it, expands it into one record per line of the poem, checks its well-formedness rules (R0 to R12)
and checks the finished poem against it. Exact things are errors; syllable, rhyme and caesura estimates
are advisory. Pure functions; no file access except `load_catalog`. Standard library only.
"""
import collections
import os
import re

SHAPES = {"couplet": 2, "tercet": 3, "quatrain": 4, "quintain": 5, "sestet": 6, "septet": 7, "octave": 8,
          "free": None}
ROLES = ("setup", "develop", "turn", "resolve")
FEET = {"iamb": 2, "trochee": 2, "spondee": 2, "anapest": 3, "dactyl": 3, "amphibrach": 3}
KINDS = ("image", "action", "statement", "pivot", "question", "address")
ENDINGS = ("stop", "run")
TAG_RE = re.compile(r"^(?:[A-Z]|x)$")

Problem = collections.namedtuple("Problem", "severity line message")
Meter = collections.namedtuple("Meter", "kind foot n lo hi pattern")
Unit = collections.namedtuple("Unit", "kind hint line")
Refrain = collections.namedtuple("Refrain", "name positions line")
Count = collections.namedtuple("Count", "lo hi")        # hi is None for `N..*`
Line = collections.namedtuple("Line", "meter ending caesura tag ends units line")   # ends: (list name, index) or None
Stanza = collections.namedtuple("Stanza", "shape count fresh rhyme role lines line")  # rhyme: tags, or None for `none`
Poem = collections.namedtuple("Poem", "named title strict flexible lets refrains stanzas")


class ParseError(Exception):
    def __init__(self, line, col, message):
        super().__init__(f"{line}:{col}: {message}")
        self.line, self.col, self.message = line, col, message


TOKEN_RE = re.compile(r"""
    (?P<space>\s+) | (?P<comment>\(\*.*?\*\)) | (?P<str>"(?:[^"\\\n]|\\.)*")
  | (?P<int>[0-9]+) | (?P<ident>[A-Za-z_][A-Za-z0-9_]*) | (?P<dots>\.\.) | (?P<punct>[{}()\[\],;=@*])
""", re.X | re.S)


def tokenize(text):
    """[(kind, value, line, col)] ending with an ('end', '', line, col) token."""
    out, pos, line, col = [], 0, 1, 1
    while pos < len(text):
        m = TOKEN_RE.match(text, pos)
        if not m:
            what = "an unterminated string" if text[pos] == '"' else f"the character {text[pos]!r}"
            raise ParseError(line, col, f"unexpected {what}")
        kind, raw = m.lastgroup, m.group()
        if kind == "str":
            out.append((kind, re.sub(r"\\(.)", r"\1", raw[1:-1]), line, col))
        elif kind not in ("space", "comment"):
            out.append((kind, raw, line, col))
        newlines = raw.count("\n")
        if newlines:
            line += newlines
            col = len(raw) - raw.rfind("\n")
        else:
            col += len(raw)
        pos = m.end()
    out.append(("end", "", line, col))
    return out


class _Parser:
    def __init__(self, text):
        self.toks = tokenize(text)
        self.i = 0

    def peek(self):
        return self.toks[self.i]

    def fail(self, expected):
        kind, value, line, col = self.peek()
        found = "the end of the text" if kind == "end" else repr(value)
        raise ParseError(line, col, f"expected {expected}, found {found}")

    def next(self):
        tok = self.toks[self.i]
        self.i += 1
        return tok

    def at(self, kind, value=None):
        tok = self.peek()
        return tok[0] == kind and (value is None or tok[1] == value)

    def take(self, kind, value=None, expected=None):
        if not self.at(kind, value):
            self.fail(expected or (repr(value) if value else kind))
        return self.next()

    def word(self, value):
        return self.take("ident", value)

    def punct(self, value):
        return self.take("punct", value)

    def integer(self, what="a whole number"):
        return int(self.take("int", expected=what)[1])

    def choice(self, options, what):
        tok = self.take("ident", expected=what)
        if tok[1] not in options:
            raise ParseError(tok[2], tok[3], f"expected {what}, found {tok[1]!r}")
        return tok[1]

    # -- the poem ----------------------------------------------------------------------------------
    def poem(self):
        self.word("poem")
        self.punct("{")
        named = title = None
        strict = flexible = False
        lets, refrains, stanzas = {}, [], []
        while not self.at("punct", "}"):
            tok = self.peek()
            if self.at("ident", "named"):
                self.next(); named = self.take("str", expected="a form name in quotes")[1]; self.punct(";")
            elif self.at("ident", "title"):
                self.next(); title = self.take("str", expected="a title in quotes")[1]; self.punct(";")
            elif self.at("ident", "strict"):
                self.next(); self.word("roles"); self.punct(";"); strict = True
            elif self.at("ident", "breaks"):
                self.next(); self.word("flexible"); self.punct(";"); flexible = True
            elif self.at("ident", "let"):
                self.next()
                name = self.take("ident", expected="a name")[1]
                if name in lets:
                    raise ParseError(tok[2], tok[3], f"'{name}' is declared twice")
                self.punct("=")
                lets[name] = self.value()
                self.punct(";")
            elif self.at("ident", "refrain"):
                refrains.append(self.refrain())
            elif self.at("ident", "stanza"):
                stanzas.append(self.stanza())
            else:
                self.fail("a declaration (named, title, strict, breaks, let, refrain) or a stanza")
        self.punct("}")
        if not self.at("end"):
            self.fail("the end of the text")
        if not stanzas:
            raise ParseError(*self.toks[1][2:4], "a poem needs at least one stanza")
        return Poem(named, title, strict, flexible, lets, refrains, stanzas)

    def value(self):
        if self.at("punct", "["):
            self.next()
            items = []
            while not self.at("punct", "]"):
                items.append(self.take("str", expected="a string")[1])
                if not self.at("punct", "]"):
                    self.punct(",")
            self.punct("]")
            return items
        return self.take("str", expected="a string or a [list]")[1]

    def refrain(self):
        line = self.word("refrain")[2]
        name = self.take("ident", expected="a refrain name")[1]
        self.word("at")
        positions = [self.integer("a line number")]
        while self.at("punct", ","):
            self.next()
            positions.append(self.integer("a line number"))
        self.punct(";")
        if len(positions) < 2:
            raise ParseError(line, 1, f"refrain {name} needs at least two line numbers")
        return Refrain(name, positions, line)

    def count(self):
        lo = self.integer("a stanza count")
        hi = lo
        if self.at("dots"):
            self.next()
            if self.at("punct", "*"):
                self.next(); hi = None
            else:
                hi = self.integer("the top of the count range")
        return Count(lo, hi)

    def tag(self, tok):
        if not TAG_RE.match(tok[1]):
            raise ParseError(tok[2], tok[3], f"expected a rhyme tag (A to Z, or x for unrhymed), found {tok[1]!r}")
        return tok[1]

    def stanza(self):
        line = self.word("stanza")[2]
        self.punct("(")
        shape = self.choice(SHAPES, "a shape (" + ", ".join(SHAPES) + ")")
        self.punct(",")
        count = self.count()
        self.punct(",")
        fresh, rhyme = False, None
        if self.at("ident", "none"):
            self.next()
        else:
            if self.at("ident", "fresh"):
                self.next(); fresh = True
            rhyme = [self.tag(self.take("ident", expected="a rhyme tag"))]
            while self.at("ident"):
                rhyme.append(self.tag(self.next()))
        role = None
        if self.at("punct", ","):
            self.next()
            role = self.choice(ROLES, "a role (" + ", ".join(ROLES) + ")")
        self.punct(")")
        self.punct("{")
        lines = []
        while self.at("ident", "line"):
            lines.append(self.line())
        if not lines:
            self.fail("a line")
        self.punct("}")
        return Stanza(shape, count, fresh, rhyme, role, lines, line)

    def meter(self):
        tok = self.take("ident", expected="a meter (a foot and number, syllables, free or stress)")
        word = tok[1]
        if word in FEET:
            return Meter("foot", word, self.integer("a foot count"), None, None, None)
        if word == "syllables":
            lo = self.integer("a syllable count")
            hi = lo
            if self.at("dots"):
                self.next(); hi = self.integer("the top of the syllable range")
            return Meter("syllables", None, None, lo, hi, None)
        if word == "free":
            return Meter("free", None, None, None, None, None)
        if word == "stress":
            s = self.take("str", expected="a stress pattern in quotes")
            if not re.fullmatch(r"[01]+", s[1]):
                raise ParseError(s[2], s[3], "a stress pattern uses only 1 (stressed) and 0 (unstressed)")
            return Meter("stress", None, None, None, None, s[1])
        raise ParseError(tok[2], tok[3], f"expected a meter (a foot and number, syllables, free or stress), found {word!r}")

    def line(self):
        line = self.word("line")[2]
        self.punct("(")
        meter = self.meter()
        self.punct(",")
        ending = self.choice(ENDINGS, "stop or run")
        self.punct(",")
        caesura = None
        if self.at("ident", "caesura"):
            self.next(); caesura = self.integer("a foot number"); self.punct(",")
        tag = self.tag(self.take("ident", expected="a rhyme tag"))
        ends = None
        if self.at("punct", ","):
            self.next(); self.word("ends")
            self.punct("@")
            name = self.take("ident", expected="a list name")[1]
            self.punct("[")
            ends = (name, self.integer("a list position"))
            self.punct("]")
        self.punct(")")
        self.punct("{")
        units = []
        while not self.at("punct", "}"):
            tok = self.peek()
            kind = self.choice(KINDS, "a unit kind (" + ", ".join(KINDS) + ")")
            self.punct("[")
            hint = self.take("str", expected="a hint in quotes")[1]
            self.punct("]")
            units.append(Unit(kind, hint, tok[2]))
            if self.at("punct", ";"):
                self.next()
        self.punct("}")
        return Line(meter, ending, caesura, tag, ends, units, line)


def parse_poem(text):
    """The Poem a skeleton describes; raises ParseError(line, col, message) on the first syntax error."""
    return _Parser(text).poem()
````

- [ ] **Step 4: Run the tests**

Run: `python3 -m unittest discover -s plugins/wrist/tests -p "test_verse_parse.py" -q 2>&1 | tail -4`
Expected: `Ran 19 tests` and `OK`.

- [ ] **Step 5: Commit**

```bash
git add plugins/wrist/skills/wrist/scripts/wrist_verse.py plugins/wrist/tests/test_verse_parse.py
git commit -m "feat(wrist): add the poem skeleton parser" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01BbGUbm5dYKZovMogE1FAjn"
```

---


### Task 2: Expansion and the skeleton rules

**Files:**
- Modify: `plugins/wrist/skills/wrist/scripts/wrist_verse.py` (append)
- Create: `plugins/wrist/tests/test_verse_rules.py`

**Interfaces:**
- Consumes: everything Task 1 produces.
- Produces in `wrist_verse`: `XLine(position, stanza_no, instance, stanza, line, tag)` (one per line of the poem; `position` and `stanza_no` count from 1; a `fresh` stanza's tag is renamed `A.1`, `A.2`, ...), `expand(poem, counts=None) -> list[XLine]` (`counts` maps a stanza index to its repeats; a range uses its lower bound), `refrain_positions(poem) -> {position: Refrain}`, `skeleton_problems(poem, concrete=True) -> list[Problem]` (severity `error`, sorted by line; rules R0, R1, R2, R3 to R5 under `strict roles;`, R8, R11; `concrete=False` skips R11 for catalog entries).

- [ ] **Step 1: Write the failing tests**

Create `plugins/wrist/tests/test_verse_rules.py`:

````python
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
````

- [ ] **Step 2: Run them to see them fail**

Run: `python3 -m unittest discover -s plugins/wrist/tests -p "test_verse_rules.py" -q 2>&1 | tail -4`
Expected: errors, `AttributeError: module 'wrist_verse' has no attribute 'expand'`.

- [ ] **Step 3: Append the implementation**

Append to the end of `plugins/wrist/skills/wrist/scripts/wrist_verse.py`:

````python


# -- expansion ----------------------------------------------------------------------------------------
XLine = collections.namedtuple("XLine", "position stanza_no instance stanza line tag")


def expand(poem, counts=None):
    """One XLine per line of the poem, in order. `counts` maps a stanza's index to its number of repeats;
    a ranged count without an entry uses its lower bound. A `fresh` stanza renames its tags per repeat
    (A becomes A.1, A.2...), so repeats do not share rhyme sounds; x stays x."""
    out, position, number = [], 0, 0
    for index, stanza in enumerate(poem.stanzas):
        repeats = (counts or {}).get(index, stanza.count.lo)
        for instance in range(1, repeats + 1):
            number += 1
            for line in stanza.lines:
                position += 1
                tag = line.tag if line.tag == "x" or not stanza.fresh else f"{line.tag}.{instance}"
                out.append(XLine(position, number, instance, stanza, line, tag))
    return out


def refrain_positions(poem):
    """{line position: refrain} for every position of every refrain."""
    return {p: r for r in poem.refrains for p in r.positions}


# -- the well-formedness rules ----------------------------------------------------------------------
HINT_REF_RE = re.compile(r"@([A-Za-z_][A-Za-z0-9_]*)(?:\[([^\]]*)\])?")
KIND_LETTER = {"image": "i", "action": "a", "statement": "s", "pivot": "p", "question": "q", "address": "d"}
ROLE_PATTERNS = {"setup": "ii[ai]s", "develop": "[ia]+s?", "turn": "p[iq][di]s", "resolve": "is"}
ROLE_TEXT = {"setup": "image image (action | image) statement", "develop": "(image | action)+ statement?",
             "turn": "pivot (image | question) (address | image) statement", "resolve": "image statement"}


def _r0(poem):
    out = []
    for stanza in poem.stanzas:
        repeated = stanza.count.lo > 1
        for line in stanza.lines:
            if line.ends:
                name, index = line.ends
                value = poem.lets.get(name)
                if not isinstance(value, list):
                    out.append(Problem("error", line.line, f"R0: `ends @{name}[{index}]` needs `let {name} = [...]` (a list)"))
                elif index >= len(value):
                    out.append(Problem("error", line.line, f"R0: `ends @{name}[{index}]` is past the end of the list "
                                                          f"(it has {len(value)} items, numbered from 0)"))
            for unit in line.units:
                if re.search(r"\$n\b", unit.hint) and not repeated:
                    out.append(Problem("error", unit.line, "R0: $n is only allowed in a stanza repeated more than once"))
                for name, index in HINT_REF_RE.findall(unit.hint):
                    value = poem.lets.get(name)
                    if value is None:
                        out.append(Problem("error", unit.line, f"R0: the hint refers to @{name}, which no `let` declares"))
                    elif index and index.strip() != "$n":
                        if not index.strip().isdigit() or not isinstance(value, list) or int(index) >= len(value):
                            out.append(Problem("error", unit.line, f"R0: @{name}[{index}] is not an item of the list"))
    return out


def _r1_r2(poem):
    out = []
    for stanza in poem.stanzas:
        lines = stanza.lines
        if stanza.rhyme is None:
            for line in lines:
                if line.tag != "x":
                    out.append(Problem("error", line.line, f"R1: the stanza says `none` but this line is tagged {line.tag}"))
        elif len(stanza.rhyme) != len(lines):
            out.append(Problem("error", stanza.line, f"R1: the rhyme scheme has {len(stanza.rhyme)} tags for {len(lines)} lines"))
        else:
            for tag, line in zip(stanza.rhyme, lines):
                if tag != line.tag:
                    out.append(Problem("error", line.line, f"R1: the scheme says {tag} but this line is tagged {line.tag}"))
        want = SHAPES[stanza.shape]
        if want is not None and len(lines) != want:
            out.append(Problem("error", stanza.line, f"R2: a {stanza.shape} has {want} lines, this stanza has {len(lines)}"))
    return out


def _r3_r4_r5(poem):
    if not poem.strict:
        return []
    out, units = [], []
    for stanza in poem.stanzas:
        kinds = [u for line in stanza.lines for u in line.units]
        units.extend(kinds)
        if stanza.role is None:
            out.append(Problem("error", stanza.line, "R3: under `strict roles;` every stanza needs a role"))
        elif not re.fullmatch(ROLE_PATTERNS[stanza.role], "".join(KIND_LETTER[u.kind] for u in kinds)):
            out.append(Problem("error", stanza.line, f"R3: a {stanza.role} stanza reads {ROLE_TEXT[stanza.role]}, "
                                                    f"this one reads {' '.join(u.kind for u in kinds) or 'nothing'}"))
        seen_image = False
        for unit in kinds:
            seen_image = seen_image or unit.kind == "image"
            if unit.kind == "statement" and not seen_image:
                out.append(Problem("error", unit.line, "R5: a statement needs an image before it in its own stanza"))
    turns = [s for s in poem.stanzas if s.role == "turn"]
    if len(turns) != 1:
        out.append(Problem("error", (turns[1] if turns else poem.stanzas[0]).line,
                           f"R4: exactly one stanza must be the turn (found {len(turns)})"))
    if units and units[-1].kind != "statement":
        out.append(Problem("error", units[-1].line, "R3: under `strict roles;` the poem ends on a statement"))
    return out


def _r8(poem):
    out, lines = [], expand(poem)
    total, claimed = len(lines), {}
    for refrain in poem.refrains:
        positions = refrain.positions
        if positions != sorted(set(positions)):
            out.append(Problem("error", refrain.line, f"R8: refrain {refrain.name}: line numbers must rise and not repeat"))
            continue
        bad = [p for p in positions if not 1 <= p <= total]
        if bad:
            out.append(Problem("error", refrain.line, f"R8: refrain {refrain.name}: line {bad[0]} is outside the poem "
                                                     f"(it has {total} lines)"))
            continue
        taken = [p for p in positions if p in claimed]
        if taken:
            out.append(Problem("error", refrain.line, f"R8: line {taken[0]} is already in refrain {claimed[taken[0]]}"))
            continue
        for p in positions:
            claimed[p] = refrain.name
        first = lines[positions[0] - 1]
        for p in positions[1:]:
            other = lines[p - 1]
            if (other.line.meter, other.line.ending, other.tag) != (first.line.meter, first.line.ending, first.tag):
                out.append(Problem("error", other.line.line, f"R8: line {p} repeats line {positions[0]} (refrain "
                                                            f"{refrain.name}) but its meter, ending or tag differs"))
    return out


def _r11(poem, concrete):
    if not concrete:
        return []
    out = []
    for stanza in poem.stanzas:
        if stanza.count.lo != stanza.count.hi:
            span = f"{stanza.count.lo}..{'*' if stanza.count.hi is None else stanza.count.hi}"
            out.append(Problem("error", stanza.line, f"R11: the count must be exact here (found {span}); choose a number"))
    return out


def skeleton_problems(poem, concrete=True):
    """Errors for the rules R0, R1, R2, R3 to R5 (strict roles only), R8 and R11, sorted by line.
    `concrete` is True for a realized structure.md, False for a catalog entry, which may use ranges."""
    out = _r0(poem) + _r1_r2(poem) + _r3_r4_r5(poem) + _r8(poem) + _r11(poem, concrete)
    return sorted(out, key=lambda p: (p.line, p.message))
````

- [ ] **Step 4: Run the tests**

Run: `python3 -m unittest discover -s plugins/wrist/tests -p "test_verse_rules.py" -q 2>&1 | tail -4`
Expected: `Ran 20 tests` and `OK`.

- [ ] **Step 5: Commit**

```bash
git add plugins/wrist/skills/wrist/scripts/wrist_verse.py plugins/wrist/tests/test_verse_rules.py
git commit -m "feat(wrist): expand poem skeletons and check their well-formedness rules" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01BbGUbm5dYKZovMogE1FAjn"
```

---


### Task 3: The verse reader, in Python and in Lua

**Files:**
- Modify: `plugins/wrist/skills/wrist/scripts/wrist_verse.py` (append)
- Create: `plugins/wrist/skills/wrist/publish/poem/verse.lua`, `plugins/wrist/tests/verse_cases.json`, `plugins/wrist/tests/test_verse_reader.py`

**Interfaces:**
- Produces in `wrist_verse`: `EN` (U+2002), `Verse(title, stanzas)` (`title` is `(line number, text)` or `None`; `stanzas` is a list of lists of `(line number, text)`; line numbers are physical lines of the file), `verse_line(raw) -> str` (each leading space, a tab counting four, an `EN`; words joined by single spaces), `read_verse(text) -> Verse`.
- Produces `publish/poem/verse.lua`: a pandoc custom reader. A `# Title` first line followed by a blank line becomes `Div` class `title`; each stanza a `Div` class `stanza` holding one `LineBlock`, a line of verse per line, a leading run of `EN` kept in the first `Str`. Nothing in a line is markup.

- [ ] **Step 1: Write the shared cases and the failing tests**

Create `plugins/wrist/tests/verse_cases.json`:

````json
[
 {
  "name": "two stanzas",
  "text": "one\ntwo\n\nthree\n",
  "title": null,
  "stanzas": [
   [
    "one",
    "two"
   ],
   [
    "three"
   ]
  ]
 },
 {
  "name": "a title",
  "text": "# Counting Down\n\nI count.\n",
  "title": "Counting Down",
  "stanzas": [
   [
    "I count."
   ]
  ]
 },
 {
  "name": "a title line with no blank after it is verse",
  "text": "# Counting\nI count.\n",
  "title": null,
  "stanzas": [
   [
    "# Counting",
    "I count."
   ]
  ]
 },
 {
  "name": "a hash line later is verse",
  "text": "one\n\n# two\n",
  "title": null,
  "stanzas": [
   [
    "one"
   ],
   [
    "# two"
   ]
  ]
 },
 {
  "name": "a title with nothing after it",
  "text": "# Alone",
  "title": "Alone",
  "stanzas": []
 },
 {
  "name": "only a title",
  "text": "# T\n",
  "title": "T",
  "stanzas": []
 },
 {
  "name": "indentation: each space and four per tab",
  "text": "a\n  b\n\tc\n",
  "title": null,
  "stanzas": [
   [
    "a",
    "  b",
    "    c"
   ]
  ]
 },
 {
  "name": "internal runs of spaces read as one",
  "text": "a   b    c\n",
  "title": null,
  "stanzas": [
   [
    "a b c"
   ]
  ]
 },
 {
  "name": "trailing space is dropped",
  "text": "a  \nb\t\n",
  "title": null,
  "stanzas": [
   [
    "a",
    "b"
   ]
  ]
 },
 {
  "name": "nothing is markup",
  "text": "*a* _b_ #c 1. d\n> e\n[f](g) `h`\n",
  "title": null,
  "stanzas": [
   [
    "*a* _b_ #c 1. d",
    "> e",
    "[f](g) `h`"
   ]
  ]
 },
 {
  "name": "leading blank lines and runs of blank lines",
  "text": "\n\none\n\n\n\ntwo\n\n",
  "title": null,
  "stanzas": [
   [
    "one"
   ],
   [
    "two"
   ]
  ]
 },
 {
  "name": "a white-space-only line separates stanzas",
  "text": "one\n   \ntwo\n",
  "title": null,
  "stanzas": [
   [
    "one"
   ],
   [
    "two"
   ]
  ]
 },
 {
  "name": "carriage returns",
  "text": "one\r\ntwo\r\n\r\nthree\r\n",
  "title": null,
  "stanzas": [
   [
    "one",
    "two"
   ],
   [
    "three"
   ]
  ]
 },
 {
  "name": "a byte order mark",
  "text": "﻿one\n",
  "title": null,
  "stanzas": [
   [
    "one"
   ]
  ]
 },
 {
  "name": "a no-break space is text, not white space",
  "text": "a b\n",
  "title": null,
  "stanzas": [
   [
    "a b"
   ]
  ]
 },
 {
  "name": "accents and quotes are kept",
  "text": "café “quoted” — dash\n",
  "title": null,
  "stanzas": [
   [
    "café “quoted” — dash"
   ]
  ]
 },
 {
  "name": "empty text",
  "text": "",
  "title": null,
  "stanzas": []
 }
]
````

Create `plugins/wrist/tests/test_verse_reader.py`:

````python
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
````

- [ ] **Step 2: Run them to see them fail**

Run: `python3 -m unittest discover -s plugins/wrist/tests -p "test_verse_reader.py" -q 2>&1 | tail -4`
Expected: errors (`AttributeError` for `read_verse`, and a pandoc failure for the missing reader).

- [ ] **Step 3: Write the Python reader**

Append to the end of `plugins/wrist/skills/wrist/scripts/wrist_verse.py`:

````python


# -- reading a poem written in verse format ---------------------------------------------------------
EN = " "
Verse = collections.namedtuple("Verse", "title stanzas")     # title: (line number, text) or None; stanzas: [[(number, text)]]


def _blank(line):
    return re.fullmatch(r"[ \t\r\f\v]*", line) is not None


def verse_line(raw):
    """The text of one line of verse as the reader keeps it: each leading space (a tab counts four) an en
    space, the words joined by single spaces, trailing white space gone."""
    lead = re.match(r"[ \t]*", raw).group()
    words = [w for w in re.split(r"[ \t\n\v\f\r]+", raw[len(lead):]) if w]
    return EN * (lead.count(" ") + 4 * lead.count("\t")) + " ".join(words)


def read_verse(text):
    """Read verse format (publish/poem/verse.lua applies the same rules): an optional first line `# Title`
    followed by a blank line, then stanzas, the runs of non-blank lines between blank ones."""
    text = text.replace("\r\n", "\n")
    if text.startswith("﻿"):
        text = text[1:]
    if not text.endswith("\n"):
        text += "\n"                       # pandoc gives a reader its input with a final newline
    lines = (text + "\n").split("\n")[:-1]
    n, i, title = len(lines), 0, None
    while i < n and _blank(lines[i]):
        i += 1
    if i < n and lines[i].startswith("# ") and i + 1 < n and _blank(lines[i + 1]):
        title = (i + 1, lines[i][2:].rstrip(" \t\n\v\f\r"))
        i += 1
    stanzas, current = [], []
    for k in range(i, n):
        if _blank(lines[k]):
            if current:
                stanzas.append(current)
                current = []
        else:
            current.append((k + 1, verse_line(lines[k])))
    if current:
        stanzas.append(current)
    return Verse(title, stanzas)
````

- [ ] **Step 4: Write the Lua reader**

Create `plugins/wrist/skills/wrist/publish/poem/verse.lua`:

````lua
-- A pandoc custom reader for wrist's plain verse. An optional first line "# Title" followed by a blank line
-- is the title (a Div of class title). Stanzas are the runs of lines between blank lines; each is a Div of
-- class stanza holding one LineBlock, a line of verse per line. Nothing in a line is markup. Each leading
-- space (a tab counts as four) becomes one en space, U+2002. A run of spaces inside a line reads as one
-- space. The rules here must stay the same as wrist_verse.py; tests/verse_cases.json is checked against both.
local EN = "\u{2002}"

local function is_blank(l) return l == nil or l:match("^[ \t\r\f\v]*$") ~= nil end

local function line_inlines(line)
  local lead = line:match("^[ \t]*")
  local body = line:sub(#lead + 1):gsub("%s+$", "")
  local indent = lead:gsub("\t", "    "):gsub(" ", EN)
  local out, first = {}, true
  for word in body:gmatch("%S+") do
    if not first then out[#out + 1] = pandoc.Space() end
    out[#out + 1] = pandoc.Str(first and (indent .. word) or word)
    first = false
  end
  return out
end

function Reader(input)
  local text = tostring(input):gsub("\r\n", "\n"):gsub("^\u{FEFF}", "")
  local lines = {}
  for l in (text .. "\n"):gmatch("(.-)\n") do lines[#lines + 1] = l end
  local blocks, i, n = {}, 1, #lines
  while i <= n and is_blank(lines[i]) do i = i + 1 end
  if i <= n and lines[i]:match("^# ") and is_blank(lines[i + 1]) and i + 1 <= n then
    local title = lines[i]:gsub("^# ", ""):gsub("%s+$", "")
    blocks[#blocks + 1] = pandoc.Div({pandoc.Para({pandoc.Str(title)})}, pandoc.Attr("", {"title"}))
    i = i + 1
  end
  local stanza = {}
  local function flush()
    if #stanza > 0 then
      blocks[#blocks + 1] = pandoc.Div({pandoc.LineBlock(stanza)}, pandoc.Attr("", {"stanza"}))
      stanza = {}
    end
  end
  while i <= n do
    if is_blank(lines[i]) then flush() else stanza[#stanza + 1] = line_inlines(lines[i]) end
    i = i + 1
  end
  flush()
  return pandoc.Pandoc(blocks)
end
````

- [ ] **Step 5: Run the tests**

Run: `python3 -m unittest discover -s plugins/wrist/tests -p "test_verse_reader.py" -q 2>&1 | tail -4`
Expected: `Ran 5 tests` and `OK` (the two `LuaReader` tests need pandoc).

- [ ] **Step 6: Commit**

```bash
git add plugins/wrist/skills/wrist/scripts/wrist_verse.py plugins/wrist/skills/wrist/publish/poem/verse.lua plugins/wrist/tests/verse_cases.json plugins/wrist/tests/test_verse_reader.py
git commit -m "feat(wrist): read plain verse, in Python and as a pandoc Lua reader" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01BbGUbm5dYKZovMogE1FAjn"
```

---


### Task 4: The poem against its skeleton: exact checks

**Files:**
- Modify: `plugins/wrist/skills/wrist/scripts/wrist_verse.py` (append)
- Create: `plugins/wrist/tests/test_verse_exact.py`

**Interfaces:**
- Consumes: `expand`, `Verse`, `read_verse`, `EN`, `Problem`.
- Produces in `wrist_verse`: `normal(text)` (lower case, curly quotes straightened, white space collapsed, punctuation stripped at both ends), `words(text)`, `spaced(text)` (`EN` to a space), `total_lines(poem)`, `stanza_count(poem)`, `poem_problems(poem, verse, titled, title) -> list[Problem]` (severity `error`, sorted by poem line number: the title line against `titled` and the premise `title`, the stanza count and each stanza's lines, the total line count, every refrain word for word as R8, every `ends` word as R12). When the total line count differs it returns before the refrain and `ends` checks. It assumes the skeleton passed `skeleton_problems`.

- [ ] **Step 1: Write the failing tests**

Create `plugins/wrist/tests/test_verse_exact.py`:

````python
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
````

- [ ] **Step 2: Run them to see them fail**

Run: `python3 -m unittest discover -s plugins/wrist/tests -p "test_verse_exact.py" -q 2>&1 | tail -4`
Expected: errors, `AttributeError: module 'wrist_verse' has no attribute 'normal'`.

- [ ] **Step 3: Append the implementation**

Append to the end of `plugins/wrist/skills/wrist/scripts/wrist_verse.py`:

````python


# -- the poem against its skeleton: exact checks ------------------------------------------------------
def normal(text):
    """A line for comparison: lower case, curly quotes straightened, white space collapsed, punctuation
    stripped at both ends."""
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    text = re.sub(r"\s+", " ", text.casefold()).strip()
    return re.sub(r"^[\W_]+|[\W_]+$", "", text)


def words(text):
    return re.findall(r"[\w']+", normal(text))


def poem_problems(poem, verse, titled, title):
    """Errors for a poem read with read_verse against its skeleton: the title line, the stanza division,
    every refrain word for word, every `ends` word. Messages come with the poem's own line numbers."""
    out, xlines = [], expand(poem)
    if verse.title and not titled:
        out.append(Problem("error", verse.title[0], "the poem has a title line but PREMISE.md says `titled: no`"))
    elif titled and not verse.title:
        out.append(Problem("error", 1, "PREMISE.md says `titled: yes` but the poem has no `# Title` line first"))
    elif titled and verse.title[1] != title:
        out.append(Problem("error", verse.title[0], f"the title line '{verse.title[1]}' differs from the "
                                                   f"premise title '{title}'"))
    want = [sum(1 for x in xlines if x.stanza_no == n) for n in range(1, (xlines[-1].stanza_no if xlines else 0) + 1)]
    have = [len(s) for s in verse.stanzas]
    if len(have) != len(want):
        first = verse.stanzas[0][0][0] if verse.stanzas else 1
        out.append(Problem("error", first, f"the skeleton has {len(want)} stanzas, the poem has {len(have)}"))
    for index, (w, h) in enumerate(zip(want, have), 1):
        if w != h:
            out.append(Problem("error", verse.stanzas[index - 1][0][0], f"stanza {index} has {h} lines, the skeleton says {w}"))
    flat = [line for stanza in verse.stanzas for line in stanza]
    if len(flat) != len(xlines):
        out.append(Problem("error", flat[0][0] if flat else 1, f"the skeleton has {len(xlines)} lines, the poem has {len(flat)}"))
        return sorted(out, key=lambda p: p.line)
    for refrain in poem.refrains:
        first = flat[refrain.positions[0] - 1]
        for p in refrain.positions[1:]:
            number, text = flat[p - 1]
            if normal(text) != normal(first[1]):
                out.append(Problem("error", number, f"R8: line {p} must repeat line {refrain.positions[0]} (refrain "
                                                   f"{refrain.name}) word for word: '{spaced(first[1])}'"))
    for x, (number, text) in zip(xlines, flat):
        if x.line.ends:
            name, index = x.line.ends
            target = words(poem.lets[name][index])
            if words(text)[-len(target):] != target:
                out.append(Problem("error", number, f"R12: line {x.position} must end with '{poem.lets[name][index]}'"))
    return sorted(out, key=lambda p: p.line)


def spaced(text):
    return text.replace(EN, " ")


def total_lines(poem):
    return len(expand(poem))


def stanza_count(poem):
    xlines = expand(poem)
    return xlines[-1].stanza_no if xlines else 0
````

- [ ] **Step 4: Run the tests**

Run: `python3 -m unittest discover -s plugins/wrist/tests -p "test_verse_exact.py" -q 2>&1 | tail -4`
Expected: `Ran 15 tests` and `OK`.

- [ ] **Step 5: Commit**

```bash
git add plugins/wrist/skills/wrist/scripts/wrist_verse.py plugins/wrist/tests/test_verse_exact.py
git commit -m "feat(wrist): check a poem's stanzas, title, refrains and end words against its skeleton" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01BbGUbm5dYKZovMogE1FAjn"
```

---


### Task 5: Advisory estimates

**Files:**
- Modify: `plugins/wrist/skills/wrist/scripts/wrist_verse.py` (append)
- Create: `plugins/wrist/tests/test_verse_estimates.py`

**Interfaces:**
- Consumes: `expand`, `Verse`, `words`, `spaced`, `Problem`.
- Produces in `wrist_verse`: `RHYME_SAME`, `STOP_ENDS`, `syllables(word)`, `line_syllables(text)`, `rhyme_key(word)`, `target_range(meter) -> (low, high) | None` (binary feet: feet times 2 up to one more; ternary: feet times 3, two fewer to one more; `syllables N..M`: that range; `stress`: the pattern's length up to one more; `free`: `None`), `estimates(poem, verse) -> list[Problem]` (severity `estimate`, every message ends `(estimate)`; empty when the poem's line count differs from the skeleton's).

- [ ] **Step 1: Write the failing tests**

Create `plugins/wrist/tests/test_verse_estimates.py`:

````python
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
````

- [ ] **Step 2: Run them to see them fail**

Run: `python3 -m unittest discover -s plugins/wrist/tests -p "test_verse_estimates.py" -q 2>&1 | tail -4`
Expected: errors, `AttributeError: module 'wrist_verse' has no attribute 'syllables'`.

- [ ] **Step 3: Append the implementation**

Append to the end of `plugins/wrist/skills/wrist/scripts/wrist_verse.py`:

````python


# -- advisory estimates -------------------------------------------------------------------------------
# English only, and rough: a vowel-group syllable counter and an ending-sound rhyme key, with no
# pronouncing dictionary. Every message is labelled an estimate and none of them blocks anything.
RHYME_SAME = {"igh": "y", "ie": "y"}
STOP_ENDS = ".,;:!?—–-…)\"'”’"


def syllables(word):
    """Estimated syllables in one word: vowel groups, less a silent final e, es or ed."""
    w = re.sub(r"[^a-z]", "", word.casefold())
    if not w:
        return 0
    n = len(re.findall(r"[aeiouy]+", w))
    if re.search(r"[^aeiouy]e$", w) and not re.search(r"[^aeiouy]le$", w):
        n -= 1
    elif re.search(r"[^aeiouytdsxzch]es$|[^aeiouytd]ed$", w) and n > 1:
        n -= 1
    return max(n, 1)


def line_syllables(text):
    return sum(syllables(w) for w in re.findall(r"[A-Za-zÀ-ɏ']+", text))


def rhyme_key(word):
    """The ending sound as spelled: the last vowel group and what follows it (keeping a silent e), with a
    few spellings of the same sound joined."""
    w = re.sub(r"[^a-z]", "", word.casefold())
    if len(w) > 3 and w.endswith("s") and not w.endswith(("ss", "us", "is")):
        w = w[:-1]                                  # a plural rhymes as its singular
    m = re.search(r"[aeiouy]+[^aeiouy]*e$", w) or re.search(r"[aeiouy]+[^aeiouy]*$", w)
    key = m.group() if m else w
    return RHYME_SAME.get(key, key)


def target_range(meter):
    """(low, high) syllables a line of this meter is expected to have, or None for no expectation."""
    if meter.kind == "foot":
        per = FEET[meter.foot]
        target = per * meter.n
        return (target, target + 1) if per == 2 else (target - 2, target + 1)
    if meter.kind == "syllables":
        return (meter.lo, meter.hi)
    if meter.kind == "stress":
        return (len(meter.pattern), len(meter.pattern) + 1)
    return None


def estimates(poem, verse):
    """Advisory Problems (severity 'estimate') for a poem whose line count matches its skeleton; an empty
    list otherwise (the exact checks report that mismatch)."""
    xlines = expand(poem)
    flat = [line for stanza in verse.stanzas for line in stanza]
    if len(flat) != len(xlines):
        return []
    out, copies = [], set()
    for refrain in poem.refrains:
        copies.update(refrain.positions[1:])
    for x, (number, text) in zip(xlines, flat):
        spec = x.line
        bare = spaced(text).strip()
        window = target_range(spec.meter)
        count = line_syllables(bare)
        if window and not window[0] <= count <= window[1]:
            span = str(window[0]) if window[0] == window[1] else f"{window[0]} to {window[1]}"
            out.append(Problem("estimate", number, f"about {count} syllable{'s' if count != 1 else ''}, the skeleton asks for {span} (estimate)"))
        if spec.ending == "stop" and bare and bare[-1] not in STOP_ENDS:
            out.append(Problem("estimate", number, "a `stop` line should end at a pause, but this one has no end punctuation (estimate)"))
        if spec.ending == "run" and bare and bare[-1] in ".!?":
            out.append(Problem("estimate", number, "a `run` line should run on, but this one ends a sentence (estimate)"))
        if spec.caesura and not re.search(r"[,;:—–]|--", bare[:-1]):
            out.append(Problem("estimate", number, f"caesura {spec.caesura}: no pause (comma, dash or colon) inside the line (estimate)"))
    groups = collections.defaultdict(list)
    for x, (number, text) in zip(xlines, flat):
        if x.tag != "x" and x.position not in copies and not x.line.ends:
            last = words(text)
            if last:
                groups[x.tag].append((number, last[-1]))
    for tag, members in groups.items():
        if len(members) < 2:
            continue
        shown = tag.split(".")[0]
        keys = collections.Counter(rhyme_key(w) for _, w in members)
        common = keys.most_common(1)[0][0]
        for number, word in members:
            if rhyme_key(word) != common:
                others = ", ".join(sorted({w for _, w in members if rhyme_key(w) == common}))
                out.append(Problem("estimate", number, f"'{word}' is under rhyme {shown} but may not rhyme with {others} (estimate)"))
        seen = collections.defaultdict(list)
        for number, word in members:
            seen[word].append(number)
        for word, numbers in seen.items():
            if len(numbers) > 1:
                out.append(Problem("estimate", numbers[1], f"the rhyme word '{word}' is used again (lines {', '.join(map(str, numbers))}) (estimate)"))
    return sorted(out, key=lambda p: (p.line, p.message))
````

- [ ] **Step 4: Run the tests**

Run: `python3 -m unittest discover -s plugins/wrist/tests -p "test_verse_estimates.py" -q 2>&1 | tail -4`
Expected: `Ran 14 tests` and `OK`.

- [ ] **Step 5: Commit**

```bash
git add plugins/wrist/skills/wrist/scripts/wrist_verse.py plugins/wrist/tests/test_verse_estimates.py
git commit -m "feat(wrist): estimate syllables, rhyme, endings and caesura as advisory findings" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01BbGUbm5dYKZovMogE1FAjn"
```

---


### Task 6: The catalog of forms and the comparison with a named form

**Files:**
- Modify: `plugins/wrist/skills/wrist/scripts/wrist_verse.py` (append)
- Create: `plugins/wrist/skills/wrist/profiles/poem/forms/*.psg` (13 files), `plugins/wrist/tests/test_verse_catalog.py`

**Interfaces:**
- Consumes: `parse_poem`, `expand`, `total_lines`, `skeleton_problems`, `Problem`.
- Produces in `wrist_verse`: `list_catalog(forms_dir) -> list[str]` (sorted names), `load_catalog(name, forms_dir) -> Poem | None` (`None` for an unknown or malformed name), `canonical_tags(xlines) -> list[str]` (tags renamed A, B, C by first appearance, `x` kept), `catalog_problems(poem, catalog, name) -> list[Problem]` (errors, each starting `named form <name>:`; compares line count, rhyme scheme up to renaming, `ends` pattern, meter where the catalog form fixes one, refrain positions, and unless the catalog form says `breaks flexible;` the stanza division; a catalog form may have at most one ranged stanza, whose repeat count is solved from the poem's line total).
- The catalog files: `ballad blank-verse couplets free-verse haiku limerick pantoum sestina sonnet-petrarchan sonnet-shakespearean tanka triolet villanelle`.

- [ ] **Step 1: Write the failing tests**

Create `plugins/wrist/tests/test_verse_catalog.py`:

````python
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
````

- [ ] **Step 2: Run them to see them fail**

Run: `python3 -m unittest discover -s plugins/wrist/tests -p "test_verse_catalog.py" -q 2>&1 | tail -4`
Expected: errors, `AttributeError: module 'wrist_verse' has no attribute 'list_catalog'`.

- [ ] **Step 3: Append the implementation**

Append to the end of `plugins/wrist/skills/wrist/scripts/wrist_verse.py`:

````python


# -- the catalog of forms ---------------------------------------------------------------------------
def list_catalog(forms_dir):
    if not os.path.isdir(forms_dir):
        return []
    return sorted(n[:-4] for n in os.listdir(forms_dir) if n.endswith(".psg"))


def load_catalog(name, forms_dir):
    """The catalog Poem called `name`; None when there is no such form."""
    path = os.path.join(forms_dir, name + ".psg")
    if not re.fullmatch(r"[a-z][a-z0-9-]*", name or "") or not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return parse_poem(fh.read())


def canonical_tags(xlines):
    """Each line's tag renamed by order of first appearance (A, B, C...), x kept: two schemes with the same
    shape compare equal whatever letters they use."""
    names, out = {}, []
    for x in xlines:
        if x.tag == "x":
            out.append("x")
            continue
        if x.tag not in names:
            names[x.tag] = chr(65 + len(names)) if len(names) < 26 else f"#{len(names)}"
        out.append(names[x.tag])
    return out


def _resolve_counts(poem, catalog, name):
    """({stanza index: repeats} for the catalog's one repeating stanza, [problems])."""
    ranged = [i for i, s in enumerate(catalog.stanzas) if s.count.lo != s.count.hi]
    total = total_lines(poem)
    if not ranged:
        want = total_lines(catalog)
        if want != total:
            return {}, [f"{name} has {want} lines, this skeleton has {total}"]
        return {}, []
    index = ranged[0]
    fixed = total_lines(catalog) - len(catalog.stanzas[index].lines) * catalog.stanzas[index].count.lo
    per = len(catalog.stanzas[index].lines)
    count = catalog.stanzas[index].count
    repeats, rest = divmod(total - fixed, per)
    span = f"{count.lo}..{'*' if count.hi is None else count.hi}"
    if total - fixed < 0 or rest or repeats < count.lo or (count.hi is not None and repeats > count.hi):
        return {}, [f"{name} repeats its stanza {span} times ({per} lines each); this skeleton's {total} lines do not fit"]
    return {index: repeats}, []


def catalog_problems(poem, catalog, name):
    """Errors where a skeleton that says `named "<name>"` differs from the catalog form: line count, rhyme
    scheme (up to renaming), refrain positions, `ends` pattern, meter (where the form fixes one) and, unless
    the form says `breaks flexible`, the stanza division."""
    counts, problems = _resolve_counts(poem, catalog, name)
    anchor = poem.stanzas[0].line
    if problems:
        return [Problem("error", anchor, f"named form {name}: {p}") for p in problems]
    ours, theirs = expand(poem), expand(catalog, counts)
    out = []

    def first_difference(kind, mine, wanted, show):
        for position, (a, b) in enumerate(zip(mine, wanted), 1):
            if a != b:
                out.append(Problem("error", ours[position - 1].line.line,
                                   f"named form {name}: {kind} differs at line {position}: {name} has {show(b)}, "
                                   f"this skeleton has {show(a)}"))
                return

    first_difference("the rhyme scheme", canonical_tags(ours), canonical_tags(theirs), lambda t: t)
    first_difference("the `ends` pattern", [x.line.ends[1] if x.line.ends else None for x in ours],
                     [x.line.ends[1] if x.line.ends else None for x in theirs],
                     lambda e: "no fixed end word" if e is None else f"end word {e}")
    first_difference("the meter", [None if t.line.meter.kind == "free" else o.line.meter for o, t in zip(ours, theirs)],
                     [None if t.line.meter.kind == "free" else t.line.meter for t in theirs],
                     lambda m: "no meter" if m is None else (f"{m.foot} {m.n}" if m.kind == "foot" else
                                                          m.kind if m.kind != "syllables" else f"{m.lo}..{m.hi} syllables"
                                                          if m.lo != m.hi else f"{m.lo} syllables"))
    mine = sorted(tuple(r.positions) for r in poem.refrains)
    wanted = sorted(tuple(r.positions) for r in catalog.refrains)
    if mine != wanted:
        out.append(Problem("error", poem.refrains[0].line if poem.refrains else anchor,
                           f"named form {name}: the refrains differ: {name} repeats lines "
                           f"{'; '.join(','.join(map(str, p)) for p in wanted) or 'none'}, this skeleton repeats "
                           f"{'; '.join(','.join(map(str, p)) for p in mine) or 'none'}"))
    if not catalog.flexible:
        def sizes(xs):
            return [sum(1 for x in xs if x.stanza_no == n) for n in range(1, (xs[-1].stanza_no if xs else 0) + 1)]
        if sizes(ours) != sizes(theirs):
            out.append(Problem("error", anchor, f"named form {name}: the stanzas should be {','.join(map(str, sizes(theirs)))} "
                                               f"lines long, this skeleton has {','.join(map(str, sizes(ours)))}"))
    return sorted(out, key=lambda p: (p.line, p.message))
````

- [ ] **Step 4: Write the catalog**

Create `plugins/wrist/skills/wrist/profiles/poem/forms/ballad.psg`:

````text
(* Ballad: rhymed quatrains, the second and fourth lines rhyming and the first and third free, alternating four and three beats. Each stanza has its own rhyme. *)
poem {
  named "ballad";
  stanza (quatrain, 2..40, fresh x A x A) {
    line (iamb 4, stop, x) { }
    line (iamb 3, stop, A) { }
    line (iamb 4, stop, x) { }
    line (iamb 3, stop, A) { }
  }
}
````

Create `plugins/wrist/skills/wrist/profiles/poem/forms/blank-verse.psg`:

````text
(* Blank verse: unrhymed iambic pentameter, any number of lines, divided into verse paragraphs as the poem needs. *)
poem {
  named "blank-verse";
  breaks flexible;
  stanza (free, 1..*, none) {
    line (iamb 5, stop, x) { }
  }
}
````

Create `plugins/wrist/skills/wrist/profiles/poem/forms/couplets.psg`:

````text
(* Couplets: pairs of rhymed lines, each pair with its own rhyme, in any meter. *)
poem {
  named "couplets";
  stanza (couplet, 1..*, fresh A A) {
    line (free, stop, A) { }
    line (free, stop, A) { }
  }
}
````

Create `plugins/wrist/skills/wrist/profiles/poem/forms/free-verse.psg`:

````text
(* Free verse: any number of unrhymed lines in any stanzas, with no meter and no repeated lines. A form that is only the absence of one; use it when the poem sets its own pattern. *)
poem {
  named "free-verse";
  breaks flexible;
  stanza (free, 1..*, none) {
    line (free, stop, x) { }
  }
}
````

Create `plugins/wrist/skills/wrist/profiles/poem/forms/haiku.psg`:

````text
(* Haiku: three lines of 5, 7 and 5 syllables. *)
poem {
  named "haiku";
  stanza (tercet, 1, none) {
    line (syllables 5, stop, x) { }
    line (syllables 7, stop, x) { }
    line (syllables 5, stop, x) { }
  }
}
````

Create `plugins/wrist/skills/wrist/profiles/poem/forms/limerick.psg`:

````text
(* Limerick: five lines, rhymed A A B B A, with three beats in the long lines and two in the short. *)
poem {
  named "limerick";
  stanza (quintain, 1, A A B B A) {
    line (syllables 8..9, stop, A) { }
    line (syllables 8..9, stop, A) { }
    line (syllables 5..6, stop, B) { }
    line (syllables 5..6, stop, B) { }
    line (syllables 8..9, stop, A) { }
  }
}
````

Create `plugins/wrist/skills/wrist/profiles/poem/forms/pantoum.psg`:

````text
(* Pantoum: four quatrains in which lines 2 and 4 of each stanza return as lines 1 and 3 of the next, and the last stanza closes the circle with lines 3 and 1 of the first. Unrhymed here, because a repeated line must keep its tag. *)
poem {
  named "pantoum";
  refrain P1 at 1, 16;
  refrain P2 at 2, 5;
  refrain P3 at 3, 14;
  refrain P4 at 4, 7;
  refrain P5 at 6, 9;
  refrain P6 at 8, 11;
  refrain P7 at 10, 13;
  refrain P8 at 12, 15;
  stanza (quatrain, 4, x x x x) {
    line (free, stop, x) { }
    line (free, stop, x) { }
    line (free, stop, x) { }
    line (free, stop, x) { }
  }
}
````

Create `plugins/wrist/skills/wrist/profiles/poem/forms/sestina.psg`:

````text
(* Sestina: six sestets and a three-line envoi. The same six end words rotate through the stanzas in the order 123456, 615243, 364125, 532614, 451362, 246531. Put the six words in the let list; the envoi here ends on words 5, 3 and 1, one end word per line. *)
poem {
  named "sestina";
  let end_words = ["word1", "word2", "word3", "word4", "word5", "word6"];
  stanza (sestet, 1, none) {
    line (free, run, x, ends @end_words[0]) { }
    line (free, run, x, ends @end_words[1]) { }
    line (free, run, x, ends @end_words[2]) { }
    line (free, run, x, ends @end_words[3]) { }
    line (free, run, x, ends @end_words[4]) { }
    line (free, run, x, ends @end_words[5]) { }
  }
  stanza (sestet, 1, none) {
    line (free, run, x, ends @end_words[5]) { }
    line (free, run, x, ends @end_words[0]) { }
    line (free, run, x, ends @end_words[4]) { }
    line (free, run, x, ends @end_words[1]) { }
    line (free, run, x, ends @end_words[3]) { }
    line (free, run, x, ends @end_words[2]) { }
  }
  stanza (sestet, 1, none) {
    line (free, run, x, ends @end_words[2]) { }
    line (free, run, x, ends @end_words[5]) { }
    line (free, run, x, ends @end_words[3]) { }
    line (free, run, x, ends @end_words[0]) { }
    line (free, run, x, ends @end_words[1]) { }
    line (free, run, x, ends @end_words[4]) { }
  }
  stanza (sestet, 1, none) {
    line (free, run, x, ends @end_words[4]) { }
    line (free, run, x, ends @end_words[2]) { }
    line (free, run, x, ends @end_words[1]) { }
    line (free, run, x, ends @end_words[5]) { }
    line (free, run, x, ends @end_words[0]) { }
    line (free, run, x, ends @end_words[3]) { }
  }
  stanza (sestet, 1, none) {
    line (free, run, x, ends @end_words[3]) { }
    line (free, run, x, ends @end_words[4]) { }
    line (free, run, x, ends @end_words[0]) { }
    line (free, run, x, ends @end_words[2]) { }
    line (free, run, x, ends @end_words[5]) { }
    line (free, run, x, ends @end_words[1]) { }
  }
  stanza (sestet, 1, none) {
    line (free, run, x, ends @end_words[1]) { }
    line (free, run, x, ends @end_words[3]) { }
    line (free, run, x, ends @end_words[5]) { }
    line (free, run, x, ends @end_words[4]) { }
    line (free, run, x, ends @end_words[2]) { }
    line (free, run, x, ends @end_words[0]) { }
  }
  stanza (tercet, 1, none) {
    line (free, run, x, ends @end_words[4]) { }
    line (free, run, x, ends @end_words[2]) { }
    line (free, run, x, ends @end_words[0]) { }
  }
}
````

Create `plugins/wrist/skills/wrist/profiles/poem/forms/sonnet-petrarchan.psg`:

````text
(* Petrarchan sonnet: an octave on two rhymes and a sestet on three, in iambic pentameter. The turn usually falls at line 9. The sestet may instead rhyme C D C D C D. The stanza breaks may be moved. *)
poem {
  named "sonnet-petrarchan";
  breaks flexible;
  stanza (octave, 1, A B B A A B B A) {
    line (iamb 5, stop, A) { }
    line (iamb 5, stop, B) { }
    line (iamb 5, stop, B) { }
    line (iamb 5, stop, A) { }
    line (iamb 5, stop, A) { }
    line (iamb 5, stop, B) { }
    line (iamb 5, stop, B) { }
    line (iamb 5, stop, A) { }
  }
  stanza (sestet, 1, C D E C D E) {
    line (iamb 5, stop, C) { }
    line (iamb 5, stop, D) { }
    line (iamb 5, stop, E) { }
    line (iamb 5, stop, C) { }
    line (iamb 5, stop, D) { }
    line (iamb 5, stop, E) { }
  }
}
````

Create `plugins/wrist/skills/wrist/profiles/poem/forms/sonnet-shakespearean.psg`:

````text
(* Shakespearean sonnet: fourteen iambic pentameter lines, three quatrains and a couplet. The usual place for the turn is line 9 or the couplet. The stanza breaks may be moved. *)
poem {
  named "sonnet-shakespearean";
  breaks flexible;
  stanza (quatrain, 1, A B A B) {
    line (iamb 5, stop, A) { }
    line (iamb 5, stop, B) { }
    line (iamb 5, stop, A) { }
    line (iamb 5, stop, B) { }
  }
  stanza (quatrain, 1, C D C D) {
    line (iamb 5, stop, C) { }
    line (iamb 5, stop, D) { }
    line (iamb 5, stop, C) { }
    line (iamb 5, stop, D) { }
  }
  stanza (quatrain, 1, E F E F) {
    line (iamb 5, stop, E) { }
    line (iamb 5, stop, F) { }
    line (iamb 5, stop, E) { }
    line (iamb 5, stop, F) { }
  }
  stanza (couplet, 1, G G) {
    line (iamb 5, stop, G) { }
    line (iamb 5, stop, G) { }
  }
}
````

Create `plugins/wrist/skills/wrist/profiles/poem/forms/tanka.psg`:

````text
(* Tanka: five lines of 5, 7, 5, 7 and 7 syllables; the third line often turns. *)
poem {
  named "tanka";
  stanza (quintain, 1, none) {
    line (syllables 5, stop, x) { }
    line (syllables 7, stop, x) { }
    line (syllables 5, stop, x) { }
    line (syllables 7, stop, x) { }
    line (syllables 7, stop, x) { }
  }
}
````

Create `plugins/wrist/skills/wrist/profiles/poem/forms/triolet.psg`:

````text
(* Triolet: eight lines on two rhymes. Line 1 returns as lines 4 and 7, and line 2 as line 8. *)
poem {
  named "triolet";
  refrain R1 at 1, 4, 7;
  refrain R2 at 2, 8;
  stanza (octave, 1, A B A A A B A B) {
    line (syllables 8, stop, A) { }
    line (syllables 8, stop, B) { }
    line (syllables 8, stop, A) { }
    line (syllables 8, stop, A) { }
    line (syllables 8, stop, A) { }
    line (syllables 8, stop, B) { }
    line (syllables 8, stop, A) { }
    line (syllables 8, stop, B) { }
  }
}
````

Create `plugins/wrist/skills/wrist/profiles/poem/forms/villanelle.psg`:

````text
(* Villanelle: nineteen lines. Two refrains, R1 and R2, return as shown, and every other line rhymes on one of
   the same two sounds. Copy this, say which lines carry which images, and keep the refrains' meter. *)
poem {
  named "villanelle";
  refrain R1 at 1, 6, 12, 18;
  refrain R2 at 3, 9, 15, 19;
  stanza (tercet, 5, A B A) {
    line (iamb 5, stop, A) { }
    line (iamb 5, stop, B) { }
    line (iamb 5, stop, A) { }
  }
  stanza (quatrain, 1, A B A A) {
    line (iamb 5, stop, A) { }
    line (iamb 5, stop, B) { }
    line (iamb 5, stop, A) { }
    line (iamb 5, stop, A) { }
  }
}
````

- [ ] **Step 5: Run the tests**

Run: `python3 -m unittest discover -s plugins/wrist/tests -p "test_verse_catalog.py" -q 2>&1 | tail -4`
Expected: `Ran 20 tests` and `OK`. The catalog tests check each form against line counts, rhyme schemes, refrain positions, stanza sizes and the sestina's end-word rotation written out in the test, not read from the files.

- [ ] **Step 6: Commit**

```bash
git add plugins/wrist/skills/wrist/scripts/wrist_verse.py plugins/wrist/skills/wrist/profiles/poem/forms plugins/wrist/tests/test_verse_catalog.py
git commit -m "feat(wrist): add the poem form catalog and compare skeletons with their named form" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01BbGUbm5dYKZovMogE1FAjn"
```

---


### Task 7: The `form` profile setting and the poem profile data

**Files:**
- Modify: `plugins/wrist/skills/wrist/scripts/wrist_profile.py`, `plugins/wrist/tests/test_profile.py`
- Create: `plugins/wrist/skills/wrist/profiles/poem/profile.json`, `questions.md`, `forms.md`, `quality.md`, `lint.json`; `plugins/wrist/tests/test_poem_profile.py`

**Interfaces:**
- Produces in `wrist_profile`: `OPTIONAL_KEYS` gains `form`; `validate` rejects a `form` that is not an object with exactly `structure` and `poem` string paths, each listed in `files` (messages: `'form' must be an object with only 'structure' and 'poem' paths`, `'form' <key> path '<path>' is not listed in 'files'`); `Profile.form` (the object or `None`); `Profile.form_paths(slug) -> (structure path, poem path) | None` (`{slug}` filled in).
- The poem profile: files `structure.md` (function `structure`) and `work/{slug}.md` (function `poem`); premise key `titled` (bool); `publish` style `poem`; `lint_format` `prose`; `title_page` false. Function `structure` has fields `Rhyme`, `Meter` and `required_when_realized` `Form`, `Lines`, `Stanzas`; function `poem` is `prose: true` with fields `Subject Speaker Tone Turn Ending Must include Must avoid Must keep`.

- [ ] **Step 1: Write the failing tests**

Create `plugins/wrist/tests/test_poem_profile.py`:

````python
import os
import re
import unittest

from support import SKILL

import wrist_profile as wp
import wrist_verse

PROFILE_DIR = os.path.join(SKILL, "profiles", "poem")


def fake(**extra):
    data = {"name": "t", "files": [{"path": "s.md", "function": "a", "order": 1},
                                   {"path": "work/{slug}.md", "function": "a", "order": 2}],
            "functions": {"a": {"heading": "a", "prose": True}}, "relations": [], "limits": {"max_prose_words": 5}}
    data.update(extra)
    return data


class FormSetting(unittest.TestCase):
    def test_a_form_names_two_listed_paths(self):
        p = wp.parse_profile(fake(form={"structure": "s.md", "poem": "work/{slug}.md"}))
        self.assertEqual(p.form, {"structure": "s.md", "poem": "work/{slug}.md"})
        self.assertEqual(p.form_paths("night"), ("s.md", "work/night.md"))

    def test_a_profile_without_a_form_has_none(self):
        p = wp.parse_profile(fake())
        self.assertIsNone(p.form)
        self.assertIsNone(p.form_paths("x"))

    def test_a_bad_form_is_rejected(self):
        for form in ("s.md", {"structure": "s.md"}, {"structure": "s.md", "poem": 3},
                     {"structure": "s.md", "poem": "work/{slug}.md", "x": "y"}):
            with self.subTest(form), self.assertRaises(wp.ProfileError) as cm:
                wp.parse_profile(fake(form=form))
            self.assertIn("'form' must be an object with only 'structure' and 'poem' paths", str(cm.exception))

    def test_a_form_path_must_be_a_listed_file(self):
        with self.assertRaises(wp.ProfileError) as cm:
            wp.parse_profile(fake(form={"structure": "nope.md", "poem": "work/{slug}.md"}))
        self.assertIn("'form' structure path 'nope.md' is not listed in 'files'", str(cm.exception))

    def test_the_other_profiles_have_no_form(self):
        for name in ("shortstory", "novel", "screenplay"):
            self.assertIsNone(wp.load_profile(name).form, name)


class PoemProfile(unittest.TestCase):
    def setUp(self):
        self.p = wp.load_profile("poem")
        self.p.set_premise({"titled": "no"})

    def test_file_shape(self):
        self.assertEqual([path for path, _ in self.p.expected_files("counting")], ["structure.md", "work/counting.md"])

    def test_settings(self):
        self.assertEqual(self.p.form, {"structure": "structure.md", "poem": "work/{slug}.md"})
        self.assertEqual(self.p.publish_style, "poem")
        self.assertEqual(self.p.lint_format, "prose")
        self.assertIs(self.p.title_page, False)
        self.assertEqual(self.p.premise_keys, {"titled": {"type": "bool"}})

    def test_functions(self):
        f = self.p.functions
        self.assertEqual(f["structure"]["required_when_realized"], ["Form", "Lines", "Stanzas"])
        self.assertEqual(f["structure"]["fields"], ["Rhyme", "Meter"])
        self.assertFalse(f["structure"]["prose"])
        self.assertTrue(f["poem"]["prose"])
        self.assertEqual(f["poem"]["fields"], ["Subject", "Speaker", "Tone", "Turn", "Ending", "Must include",
                                               "Must avoid", "Must keep"])

    def test_questions(self):
        self.assertEqual({q.id for q in self.p.questions if q.required}, {"subject", "form", "tone", "audience", "length"})
        self.assertEqual({q.id for q in self.p.questions if not q.required},
                         {"speaker", "occasion", "rhyme", "images", "avoid", "titled", "epigraph", "dedication", "keep"})

    def test_every_premise_key_has_a_question(self):
        self.assertEqual({self.p.question_key(q.id) for q in self.p.questions} - {None}, set(self.p.premise_keys))

    def test_titled_is_yes_or_no_and_defaults_to_no(self):
        self.assertEqual(self.p.resolve_options({})[0], {"titled": False})
        self.assertEqual(self.p.resolve_options({"titled": "yes"})[0], {"titled": True})
        self.assertEqual(self.p.resolve_options({"titled": "maybe"})[1][0][0], "titled")


class PoemContent(unittest.TestCase):
    def read(self, name):
        with open(os.path.join(PROFILE_DIR, name), encoding="utf-8") as fh:
            return fh.read()

    def test_forms_md_covers_every_catalog_form(self):
        text = self.read("forms.md")
        for name in wrist_verse.list_catalog(os.path.join(PROFILE_DIR, "forms")):
            self.assertIn(f"## {name}\n", text, name)

    def test_the_questions_name_every_catalog_form(self):
        text = self.read("questions.md")
        for name in wrist_verse.list_catalog(os.path.join(PROFILE_DIR, "forms")):
            self.assertIn(name, text, name)

    def test_quality_md_has_its_three_parts_and_the_prompt_rules(self):
        text = self.read("quality.md")
        for heading in ("## Clichés and stock moves", "## Marks of low quality", "## Judgment checklist"):
            self.assertIn(heading, text)
        for phrase in ("At most one simile", "Delete the last line", "unjustifiable", "Must keep:", "moment"):
            self.assertIn(phrase, text, phrase)
        self.assertGreaterEqual(text.count("- [ ] "), 10)

    def test_every_lint_pattern_matches_its_positive_and_not_its_negative(self):
        items = wp.load_profile("poem").lint_items()
        self.assertGreaterEqual(len(items), 15)
        for item in items:
            with self.subTest(item["id"]):
                rx = re.compile(item["pattern"], re.IGNORECASE)
                self.assertTrue(rx.search(item["positive"]), "positive sample does not match")
                self.assertFalse(rx.search(item["negative"]), "negative sample matches")

    def test_the_banned_words_are_all_linted(self):
        items = wp.load_profile("poem").lint_items()
        for word in ("starlight", "threshold", "void", "cathedral", "hymn", "cradle", "unfold", "becoming", "luminous",
                     "tapestry", "whisper", "echo", "shatter", "dance", "ache", "infinite", "sacred", "silence", "moment"):
            self.assertTrue(any(re.search(i["pattern"], word, re.I) for i in items), word)
````

- [ ] **Step 2: Run them to see them fail**

Run: `python3 -m unittest discover -s plugins/wrist/tests -p "test_poem_profile.py" -q 2>&1 | tail -4`
Expected: failures and errors (`'form'` is an unknown key; `no profile 'poem'`).

- [ ] **Step 3: Apply the profile engine change**

Write this to `/tmp/profile.patch` and apply it:

````diff
--- a/plugins/wrist/skills/wrist/scripts/wrist_profile.py
+++ b/plugins/wrist/skills/wrist/scripts/wrist_profile.py
@@ -16,7 +16,7 @@
 SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
 QUESTION_RE = re.compile(r"^-\s+\[(required|deferrable)\]\s+([a-z0-9]+(?:-[a-z0-9]+)*):\s+(\S.*)$")
 TOP_KEYS = {"name", "files", "functions", "relations", "limits"}
-OPTIONAL_KEYS = {"title_page", "premise_keys", "publish", "lint_format"}    # title_page: a separate title page when published (default true)
+OPTIONAL_KEYS = {"title_page", "premise_keys", "publish", "lint_format", "form"}    # title_page: a separate title page when published (default true)
 FUNCTION_KEYS = {"heading", "fields", "children", "prose", "required_when_realized", "sequence", "heading_field"}
 FILE_KEYS = {"path", "function", "order", "when", "family"}
 KEY_SETTINGS = {"type", "min", "max", "required"}
@@ -140,6 +140,14 @@
             raise ProfileError(f"file '{f['path']}': 'family' must name an int premise key")
         if ("{n}" in f["path"]) != ("family" in f):
             raise ProfileError(f"file '{f['path']}': a family path must contain {{n}}, and only a family path may")
+    form = data.get("form")
+    if form is not None:
+        if not (isinstance(form, dict) and set(form) == {"structure", "poem"}
+                and all(isinstance(v, str) for v in form.values())):
+            raise ProfileError("'form' must be an object with only 'structure' and 'poem' paths")
+        for key, path in form.items():
+            if path not in seen:
+                raise ProfileError(f"'form' {key} path '{path}' is not listed in 'files'")
     if not _strings(data["relations"]):
         raise ProfileError("'relations' must be a list of words")
     limits = data["limits"]
@@ -173,6 +181,7 @@
         self.premise_keys = data.get("premise_keys", {})
         self.publish_style = (data.get("publish") or {}).get("style")
         self.lint_format = data.get("lint_format", "prose")
+        self.form = data.get("form")        # {"structure": path, "poem": path} for a poem profile, else None
         self.questions = questions
         self.directory = directory
         self.options = {}              # resolved premise values; filled by set_premise
@@ -255,6 +264,12 @@
                 out.append((path, f["function"]))
         return out
 
+    def form_paths(self, slug):
+        """(structure path, poem path) of a poem profile with {slug} filled in; None without a `form`."""
+        if not self.form:
+            return None
+        return self.form["structure"], self.form["poem"].replace("{slug}", slug)
+
     def function_for(self, rel, slug, options=None):
         return dict(self.expected_files(slug, options)).get(rel)
 
````

Run: `git apply /tmp/profile.patch && git diff --stat`
Expected: `wrist_profile.py` changed.

- [ ] **Step 4: Write the profile data**

Create `plugins/wrist/skills/wrist/profiles/poem/profile.json`:

````json
{
  "name": "poem",
  "title_page": false,
  "publish": {"style": "poem"},
  "lint_format": "prose",
  "form": {"structure": "structure.md", "poem": "work/{slug}.md"},
  "premise_keys": {
    "titled": {"type": "bool"}
  },
  "files": [
    {"path": "structure.md", "function": "structure", "order": 1},
    {"path": "work/{slug}.md", "function": "poem", "order": 2}
  ],
  "functions": {
    "structure": {
      "heading": "structure",
      "fields": ["Rhyme", "Meter"],
      "required_when_realized": ["Form", "Lines", "Stanzas"]
    },
    "poem": {
      "heading": "poem",
      "fields": ["Subject", "Speaker", "Tone", "Turn", "Ending", "Must include", "Must avoid", "Must keep"],
      "prose": true
    }
  },
  "relations": ["appears", "mentions", "sets up", "pays off", "realizes"],
  "limits": {"max_prose_words": 120}
}
````

Create `plugins/wrist/skills/wrist/profiles/poem/questions.md`:

````markdown
# Premise questions: poem

Ask these in the premise phase, a few at a time, in plain language. A `required` question must be answered or
recorded as an `*UNKNOWN*:` before generation; a `deferrable` question may be left out (write `none (skipped on
purpose)` so `check` stops warning about it). The id is the key used in `wrist/PREMISE.md`.

One answer decides what is printed, so it goes in the `PREMISE.md` front matter as well: `titled` (`yes` or `no`,
default `no`). A question whose id is a front matter key counts as answered when the front matter has the key.
The front matter `title:` is always needed: when `titled` is `yes` it is the title printed above the poem, and
when `no` it is only a working title for the file names and the metadata.

## The poem

- [required] subject: What is the poem about, in a sentence? Name the concrete thing, place or moment it starts from, not the theme.
- [required] form: Which form (see forms.md: sonnet-shakespearean, sonnet-petrarchan, villanelle, sestina, pantoum, haiku, tanka, limerick, triolet, ballad, couplets, blank-verse, free-verse), `custom`, or "choose for me"?
- [required] tone: What tone should the poem hold, and where may it turn?
- [required] audience: Who is it for (yourself, a person, an occasion, a readership)?
- [required] length: How long, in lines? If the form fixes it, say "the form's own".

## What you already know

- [deferrable] speaker: Who is speaking, and to whom?
- [deferrable] occasion: Is it written for an occasion (a date, an event, a person)?
- [deferrable] rhyme: Any preference on rhyme and meter (rhymed, unrhymed, strict, loose)?
- [deferrable] images: Which images, objects or sounds should be in it?
- [deferrable] avoid: What do you want kept out (subjects, words, images, tones)?
- [deferrable] titled: Does the poem carry a title? Answer `yes` or `no`; the default is no, and if yes, give the title.
- [deferrable] epigraph: An epigraph, with its source?
- [deferrable] dedication: A dedication?
- [deferrable] keep: Is there a detail, word or digression that matters to you for reasons the poem need not give, and that must stay even if an editor would cut it?
````

Create `plugins/wrist/skills/wrist/profiles/poem/forms.md`:

````markdown
# Poem forms

Each form is a skeleton in `forms/<name>.psg`. Copy it into `structure.md`, keep its line count, rhyme scheme,
refrains and meter (the `named` line makes `verse` check that you did), and add `image[...]`-style unit hints
if you want them. `references/psg.md` is the grammar. A form is a promise to the reader, kept or broken on
purpose: if the poem needs a different shape, say `custom` and write your own skeleton.

## sonnet-shakespearean
Fourteen lines of iambic pentameter: three quatrains (A B A B, C D C D, E F E F) and a couplet (G G). The argument
usually turns at line 9 or in the couplet. Fits an argument or a change of mind. Watch: the couplet that only
sums up, and rhymes that bend the sense. The stanza breaks may be moved.

## sonnet-petrarchan
An octave (A B B A A B B A) and a sestet (C D E C D E, or C D C D C D), in iambic pentameter, turning at line 9.
Fits a problem and its answer. Watch: English has fewer rhymes, so the A and B sounds tire. The breaks may be moved.

## villanelle
Nineteen lines in five tercets and a quatrain on two rhymes. Line 1 returns as lines 6, 12 and 18; line 3 as lines
9, 15 and 19. Fits an obsession or a thing that cannot be put down. Watch: the refrains must change meaning as the
poem goes, or the form is only repetition. Refrains keep their meter and tag.

## sestina
Six sestets and a three-line envoi, all on six end words that rotate (123456, 615243, 364125, 532614, 451362,
246531); the envoi here ends on words 5, 3 and 1. Fits a subject with six facets. Put the six words in the `let`
list. Watch: choose words that bend (a noun that is also a verb); avoid abstractions.

## pantoum
Four quatrains in which lines 2 and 4 of each stanza return as lines 1 and 3 of the next; the last stanza closes the
circle with lines 3 and 1 of the first. Unrhymed here. Fits memory and circling. Watch: repeated lines must read
differently in a new place.

## haiku
Three lines of 5, 7 and 5 syllables: an image, a cut, a second image. Watch: the syllable count is the least of it.

## tanka
Five lines of 5, 7, 5, 7, 7 syllables; the third line often turns.

## limerick
Five lines rhymed A A B B A, with three beats in the long lines and two in the short. Comic.

## triolet
Eight lines on two rhymes; line 1 returns as lines 4 and 7, line 2 as line 8. Fits a short thought that changes.

## ballad
Rhymed quatrains, lines 2 and 4 rhyming, alternating four and three beats; each stanza has its own rhyme. Fits a story.

## couplets
Pairs of rhymed lines, each pair with its own rhyme. Watch: the sing-song.

## blank-verse
Unrhymed iambic pentameter, any length. Fits speech and argument.

## free-verse
Any lines, any stanzas, no meter, no repeated lines. Watch: the line break must still do work.
````

Create `plugins/wrist/skills/wrist/profiles/poem/quality.md`:

````markdown
# Quality for a poem

The target is a poem an editor or a prize jury would stop for. Copy the rules that apply into each stand-in's
`Rules:` during generation; check the poem against all of them during realization. The searchable items are in
`lint.json` (run `wrist_check.py lint`); `wrist_check.py verse` checks the poem against its skeleton; the rest need a
reader's judgment. Form-required repetition (refrains, sestina end words, rhyme words) is exempt from the rules
about repeating words.

## Clichés and stock moves

Images
- A simile reflexively ("like a", "as if"). At most one in the poem, and only if the poem cannot survive without it.
- The glamorous word where a plain one would do: starlight, threshold, void, cathedral, hymn, cradle, unfold, becoming,
  luminous, tapestry, whisper, echo, shatter, dance, ache, infinite, sacred, silence (as a noun of profundity).
- The abstraction in place of the thing: soul, eternity, destiny, darkness.
- The sunset ending; the moon and June rhyme; heart and part; fire and desire; love and above.
- Archaic diction ("thee", "o'er", "'twas") and a word inverted to make a rhyme.

Feeling
- Telling the reader that anyone wept, trembled or felt something profound.
- Announcing that a moment matters, or using the word "moment".
- Flattering the subject (a machine made secretly tender) or the reader (a line designed to be quoted).

Structure
- A last line or stanza that explains the poem, a moral, an aphorism, a summary.
- Sections of equal length, two balanced voices, a tidy coda (unless the form requires it).
- One-word thematic section titles; a title that summarizes the poem.
- Allusion to a famous work that a well-read reader matches in one guess.

## Marks of low quality

- A rhyme that bends the sense, or padding to reach a syllable count.
- Every line end-stopped, or every line enjambed; breaks at commas and clause ends, which waste the break.
- A steady, mellow rhythm across the whole poem; every line the same shape and length.
- An image used once and then explained.
- No turn: the last line says what the first said.
- Detail that could belong to any poem; no object that only someone who was there would know.
- A rhyme word used twice for rhyme, unless it is meant.

## Judgment checklist

Work through this in the review pass, with the poem and its skeleton open. Mark an item only when you have
checked it against the text.

- [ ] Read aloud, each line has its own sound; the texture varies (a lush line, a flat one, a monosyllable).
- [ ] The line breaks do work: break against the syntax at least half the time.
- [ ] Every image is concrete and unglamorous, something a person would know only by having been there.
- [ ] At most one simile, and the poem needs it.
- [ ] Delete the last line: is the poem better? If so, delete it (or change the skeleton and the form's promise).
- [ ] Every word on the ban list is replaced with a specific object, or kept on purpose.
- [ ] Emotion and significance are withheld: chairs left behind, and stop.
- [ ] The turn changes the poem; the ending lands without explaining.
- [ ] One thing is left unresolved.
- [ ] There is one unjustifiable choice, a detail a careful editor would cut and you keep without explaining it (`Must keep:`).
- [ ] The form is kept, or broken on purpose; refrains change meaning as they return.
- [ ] The title, if any, is oblique and does not summarize.
````

Create `plugins/wrist/skills/wrist/profiles/poem/lint.json`:

````json
{
 "items": [
  {
   "id": "lofty-noun",
   "pattern": "\\b(?:starlight|thresholds?|void|cathedrals?|hymns?|cradl(?:e|es|ed|ing)|luminous|tapestr(?:y|ies)|infinite|sacred)\\b",
   "label": "glamorous poem word",
   "note": "The word that sounds like it belongs in a poem is a reason to cut it; name a specific object.",
   "scope": "anywhere",
   "positive": "A cathedral of starlight.",
   "negative": "A kitchen with a cracked sink."
  },
  {
   "id": "unfold-becoming",
   "pattern": "\\b(?:unfold(?:s|ed|ing)?|becoming)\\b",
   "label": "glamorous poem word",
   "note": "Say what physically happens.",
   "scope": "anywhere",
   "positive": "Her grief unfolds.",
   "negative": "Her grief is a chair."
  },
  {
   "id": "whisper",
   "pattern": "\\bwhisper(?:s|ed|ing)?\\b",
   "label": "glamorous poem word",
   "note": "Say who spoke, how quietly, and what was said.",
   "scope": "anywhere",
   "positive": "The wind whispered.",
   "negative": "The wind stopped."
  },
  {
   "id": "echo",
   "pattern": "\\becho(?:es|ed|ing)?\\b",
   "label": "glamorous poem word",
   "note": "An echo is a stock effect; give the sound its source.",
   "scope": "anywhere",
   "positive": "Her name echoed.",
   "negative": "Her name was shouted twice."
  },
  {
   "id": "shatter",
   "pattern": "\\bshatter(?:s|ed|ing)?\\b",
   "label": "glamorous poem word",
   "note": "Break the thing in a specific way.",
   "scope": "anywhere",
   "positive": "The glass shattered.",
   "negative": "The glass cracked in two."
  },
  {
   "id": "dance",
   "pattern": "\\bdanc(?:e|es|ed|ing)\\b",
   "label": "glamorous poem word",
   "note": "Things in poems dance too often; describe the movement.",
   "scope": "anywhere",
   "positive": "Light dances on the water.",
   "negative": "Light lay on the water."
  },
  {
   "id": "ache",
   "pattern": "\\bach(?:e|es|ed|ing)\\b",
   "label": "named feeling",
   "note": "Withhold the emotion; show what the body or the room does.",
   "scope": "anywhere",
   "positive": "My heart aches.",
   "negative": "I achieved little."
  },
  {
   "id": "silence",
   "pattern": "\\bsilen(?:ce|ces|t)\\b",
   "label": "named profundity",
   "note": "Silence as a noun of profundity is a ban-list word; say what is actually quiet.",
   "scope": "anywhere",
   "positive": "The silence of her leaving.",
   "negative": "The radio was off."
  },
  {
   "id": "moment",
   "pattern": "\\bmoments?\\b",
   "label": "announced significance",
   "note": "Do not announce that a moment matters.",
   "scope": "anywhere",
   "positive": "In that moment I knew.",
   "negative": "On Tuesday I knew."
  },
  {
   "id": "simile-like",
   "pattern": "\\blike (?:a|an|the|some|my|your|his|her)\\b",
   "label": "simile",
   "note": "At most one simile in the poem; prefer describing the thing until it carries its own weight.",
   "scope": "anywhere",
   "positive": "Like a bird she left.",
   "negative": "I like birds."
  },
  {
   "id": "simile-as-if",
   "pattern": "\\bas (?:if|though)\\b",
   "label": "simile",
   "note": "A reflexive simile; cut it or keep it only if the poem cannot survive without it.",
   "scope": "anywhere",
   "positive": "As if the room breathed.",
   "negative": "As the room emptied, I left."
  },
  {
   "id": "told-emotion",
   "pattern": "\\b(?:wept|weeping|sobbed|trembled|trembling)\\b",
   "label": "told emotion",
   "note": "Describe the chairs left behind and stop.",
   "scope": "anywhere",
   "positive": "She wept at the gate.",
   "negative": "She locked the gate."
  },
  {
   "id": "tears-fall",
   "pattern": "\\btears (?:fell|fall|ran|run|streamed|welled|spilled)\\b",
   "label": "stock reaction",
   "note": "Let the reader supply the tears.",
   "scope": "anywhere",
   "positive": "Tears fell on the page.",
   "negative": "Rain fell on the page."
  },
  {
   "id": "abstraction",
   "pattern": "\\b(?:souls?|eternity|destiny|darkness)\\b",
   "label": "abstraction in place of an image",
   "note": "Name the thing the abstraction stands for.",
   "scope": "anywhere",
   "positive": "Into the darkness of eternity.",
   "negative": "Into the cellar."
  },
  {
   "id": "archaic",
   "pattern": "\\b(?:thee|thou|thy|thine|doth|hath)\\b|\\b(?:o|ne)['’]er\\b|['’]t(?:was|is)\\b",
   "label": "archaic diction",
   "note": "Archaic words are a fingerprint of the borrowed poem; use the speaker's own.",
   "scope": "anywhere",
   "positive": "O'er the hill thou goest.",
   "negative": "Over the hill you go."
  },
  {
   "id": "sunset-ending",
   "pattern": "\\b(?:sunsets?|setting sun|sun (?:sank|sinks|set|fades|faded))\\b",
   "label": "stock ending",
   "note": "The sunset ending is the oldest closing image; find the one only this poem has.",
   "scope": "anywhere",
   "positive": "The sunset closed the day.",
   "negative": "The shop closed at six."
  },
  {
   "id": "stock-rhyme-pair",
   "pattern": "\\b(?:moon and june|heart and part|fire and desire|love and above)\\b",
   "label": "stock rhyme",
   "note": "These pairs are decades worn; change one end word and the line it ends.",
   "scope": "anywhere",
   "positive": "her heart and part of mine",
   "negative": "her coat and her keys"
  }
 ]
}
````

- [ ] **Step 5: Fix the one existing test that used `poem` as an unknown profile name**

`plugins/wrist/tests/test_profile.py` asked for the profile `poem` to see the error for a missing one. Now `poem` exists. Apply this patch:

````diff
--- a/plugins/wrist/tests/test_profile.py
+++ b/plugins/wrist/tests/test_profile.py
@@ -129,8 +129,8 @@
 class Loading(unittest.TestCase):
     def test_unknown_profile_lists_what_exists(self):
         with self.assertRaises(wp.ProfileError) as cm:
-            wp.load_profile("poem")
-        self.assertIn("no profile 'poem'", str(cm.exception))
+            wp.load_profile("sonnet")
+        self.assertIn("no profile 'sonnet'", str(cm.exception))
         self.assertIn("shortstory", str(cm.exception))
 
     def test_a_name_cannot_climb_out_of_the_profiles_folder(self):
````

Write it to `/tmp/testprofile.patch` and run `git apply /tmp/testprofile.patch`.

- [ ] **Step 6: Run the tests and the whole suite**

Run: `python3 -m unittest discover -s plugins/wrist/tests -p "test_poem_profile.py" -q 2>&1 | tail -4`
Expected: `Ran 16 tests` and `OK`.

Run: `python3 -m unittest discover -s plugins/wrist/tests -q 2>&1 | tail -3`
Expected: `OK` (388 earlier tests plus the 93 verse tests plus these 16).

- [ ] **Step 7: Commit**

```bash
git add plugins/wrist/skills/wrist/scripts/wrist_profile.py plugins/wrist/skills/wrist/profiles/poem plugins/wrist/tests/test_poem_profile.py plugins/wrist/tests/test_profile.py
git commit -m "feat(wrist): add the form profile setting and the poem profile data" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01BbGUbm5dYKZovMogE1FAjn"
```

---


### Task 8: The poem publishing style

**Files:**
- Modify: `plugins/wrist/skills/wrist/scripts/wrist_publish.py`, `plugins/wrist/skills/wrist/scripts/wrist_check.py` (`cmd_publish` only)
- Create: `plugins/wrist/skills/wrist/publish/poem/poem.lua`, `poem.typ`, `poem.css`; `plugins/wrist/tests/test_poem_publish.py`

**Interfaces:**
- Consumes: `Profile.publish_style`, `verse.lua` from Task 3.
- Produces in `wrist_publish`: `STYLES` gains `poem`; `POEM_KEYS = ("dedication", "epigraph")`; `plan_poem(inputs, meta, out_dir, slug, publish_dir) -> [("epub", argv), ("pdf", argv)]` (`meta` has `title`, `author`, optional `language`, `trim`, `font`, `titled`, `dedication`, `epigraph`; both builds read through `publish/poem/verse.lua` and the filter `poem.lua`; the EPUB passes `--epub-title-page=false`; `titled=true` is passed only when `meta["titled"]` is truthy).
- `cmd_publish`: style `poem` builds `plan_poem(sources, meta, ...)` with `meta["titled"]` from the profile's resolved `titled` option.
- The filter turns each `stanza` Div into `#stanza(keep)[` with one `#vl(<lead>em)[...]` per line (`keep` true up to 16 lines); the EPUB gets a heading first (so pandoc files nothing before it in a section of its own), id `poem-title` when titled and `poem-hidden-title` when not, then the dedication, byline and epigraph.

- [ ] **Step 1: Write the failing tests**

Create `plugins/wrist/tests/test_poem_publish.py`:

````python
import os
import unittest

from support import SKILL

import wrist_profile as wp
import wrist_publish


class PoemPlan(unittest.TestCase):
    META = {"title": "Counting", "author": "Ada Example", "language": "en"}
    PUBLISH_DIR = os.path.join(SKILL, "publish")

    def plan(self, **meta):
        return dict(wrist_publish.plan_poem(["work/counting.md"], dict(self.META, **meta), "output", "counting", self.PUBLISH_DIR))

    def test_the_style_resolves(self):
        self.assertEqual(wrist_publish.style_for(wp.load_profile("poem")), "poem")

    def test_both_formats_read_verse_through_the_custom_reader_and_filter(self):
        d = os.path.join(self.PUBLISH_DIR, "poem")
        for argv in self.plan().values():
            self.assertEqual(argv[:4], ["pandoc", "--from", os.path.join(d, "verse.lua"), "work/counting.md"])
            self.assertEqual(argv[argv.index("--lua-filter") + 1], os.path.join(d, "poem.lua"))
        for name in ("verse.lua", "poem.lua", "poem.typ", "poem.css"):
            self.assertTrue(os.path.isfile(os.path.join(d, name)), name)

    def test_the_pdf_uses_the_template_and_the_epub_the_stylesheet(self):
        d = os.path.join(self.PUBLISH_DIR, "poem")
        pdf, epub = self.plan()["pdf"], self.plan()["epub"]
        self.assertEqual(pdf[pdf.index("--template") + 1], os.path.join(d, "poem.typ"))
        self.assertIn("--pdf-engine=typst", pdf)
        self.assertEqual(epub[epub.index("--css") + 1], os.path.join(d, "poem.css"))
        self.assertIn("--epub-title-page=false", epub)

    def test_titled_dedication_and_epigraph_reach_both_formats_only_when_set(self):
        plan = self.plan(titled=True, dedication="for M.", epigraph="an epigraph")
        for argv in plan.values():
            for item in ("titled=true", "dedication=for M.", "epigraph=an epigraph"):
                self.assertIn(item, argv)
        for argv in self.plan().values():
            self.assertFalse([a for a in argv if a.startswith(("titled=", "dedication=", "epigraph="))])

    def test_review_focus_special_characters_stay_one_intact_argument(self):
        text = 'A & B #1 @home $5 "Q" café *x* \\ [w]'
        for argv in self.plan(title=text, epigraph=text, dedication=text).values():
            for key in ("title", "epigraph", "dedication"):
                self.assertIn(f"{key}={text}", argv)
````

- [ ] **Step 2: Run them to see them fail**

Run: `python3 -m unittest discover -s plugins/wrist/tests -p "test_poem_publish.py" -q 2>&1 | tail -4`
Expected: failures and errors (`plan_poem` missing, `poem.lua` missing).

- [ ] **Step 3: Apply the publishing changes**

Write each patch to a file and apply both:

`/tmp/publish.patch`:

````diff
--- a/plugins/wrist/skills/wrist/scripts/wrist_publish.py
+++ b/plugins/wrist/skills/wrist/scripts/wrist_publish.py
@@ -102,9 +102,10 @@
                                f"{proc.stderr.strip() or proc.stdout.strip()}")
 
 
-STYLES = ("story", "book", "screenplay")
+STYLES = ("story", "book", "screenplay", "poem")
 NUMBER_WORDS = ("ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN")
 SCREENPLAY_KEYS = ("based_on", "draft", "contact")
+POEM_KEYS = ("dedication", "epigraph")
 
 
 def style_for(profile):
@@ -157,6 +158,31 @@
     if meta.get("trim"):
         pdf += ["-V", f"papersize={meta['trim']}"]
     if meta.get("font"):
+        pdf += ["-V", f"mainfont={meta['font']}"]
+    pdf += ["-o", f"{out_dir}/{slug}.pdf"]
+    return [("epub", epub), ("pdf", pdf)]
+
+
+def plan_poem(inputs, meta, out_dir, slug, publish_dir):
+    """[(kind, argv)] for a poem: verse read by the custom reader, the Typst filter for the PDF. `meta` has
+    title, author, optional language, trim, font, titled (print the title), dedication and epigraph."""
+    folder = os.path.join(publish_dir, "poem")
+    common = ["pandoc", "--from", os.path.join(folder, "verse.lua"), *inputs,
+              "--metadata", f"title={meta['title']}",
+              "--metadata", f"author={meta['author']}",
+              "--metadata", f"lang={meta.get('language') or 'en'}"]
+    if meta.get("titled"):
+        common += ["--metadata", "titled=true"]
+    for key in POEM_KEYS:
+        if meta.get(key):
+            common += ["--metadata", f"{key}={meta[key]}"]
+    filt = ["--lua-filter", os.path.join(folder, "poem.lua")]
+    epub = common + ["--to", "epub3", "--epub-title-page=false", "--css", os.path.join(folder, "poem.css")] + filt \
+        + ["-o", f"{out_dir}/{slug}.epub"]
+    pdf = common + filt + ["--template", os.path.join(folder, "poem.typ"), "--pdf-engine=typst"]
+    if meta.get("trim"):
+        pdf += ["-V", f"papersize={meta['trim']}"]
+    if meta.get("font"):
         pdf += ["-V", f"mainfont={meta['font']}"]
     pdf += ["-o", f"{out_dir}/{slug}.pdf"]
     return [("epub", epub), ("pdf", pdf)]
````

`/tmp/check1.patch`:

````diff
--- a/plugins/wrist/skills/wrist/scripts/wrist_check.py
+++ b/plugins/wrist/skills/wrist/scripts/wrist_check.py
@@ -1212,7 +1212,12 @@
             "language": pm.front.get("language", (0, "en"))[1], "trim": pm.front.get("trim", (0, ""))[1],
             "font": pm.front.get("font", (0, ""))[1], "title_page": profile.title_page}
     markers = []
-    if style == "screenplay":
+    if style == "poem":
+        for key in wrist_publish.POEM_KEYS:
+            meta[key] = pm.front.get(key, (0, ""))[1]
+        meta["titled"] = bool(profile.options.get("titled"))
+        plan = wrist_publish.plan_poem(sources, meta, "output", slug, PUBLISH_DIR)
+    elif style == "screenplay":
         for key in wrist_publish.SCREENPLAY_KEYS:
             meta[key] = pm.front.get(key, (0, ""))[1]
         inputs = list(sources)
````

Run: `git apply /tmp/publish.patch /tmp/check1.patch && git diff --stat`
Expected: `wrist_publish.py` and `wrist_check.py` changed.

- [ ] **Step 4: Write the filter, the template and the stylesheet**

Create `plugins/wrist/skills/wrist/publish/poem/poem.lua`:

````lua
-- Turns the reader's stanza Divs into calls of the layout functions in poem.typ for the PDF, and builds
-- the heading block for the EPUB. The title Div the reader emits is dropped: the title is the PREMISE title,
-- printed only when the poem is titled.
local EN = "\u{2002}"
local KEEP_MAX = 16          -- a stanza of up to this many lines is kept whole on a page

local function titled(meta)
  return meta.titled ~= nil and (meta.titled == true or pandoc.utils.stringify(meta.titled) == "true")
end

local function text_of(meta, key)
  local v = meta[key]
  return v and pandoc.utils.stringify(v) or ""
end

-- A leading run of en spaces is measured and removed: the layout function turns it into a Typst horizontal
-- space (half an em each), so the typesetter cannot trim it, and hangs wrapped lines past it.
local function split_indent(inlines)
  local out, lead = {}, 0
  for i, inline in ipairs(inlines) do
    if i == 1 and inline.t == "Str" then
      local rest = inline.text
      while rest:sub(1, #EN) == EN do lead = lead + 1; rest = rest:sub(#EN + 1) end
      out[#out + 1] = pandoc.Str(rest)
    else
      out[#out + 1] = inline
    end
  end
  return out, lead * 0.5
end

function Pandoc(doc)
  local blocks = {}
  for _, b in ipairs(doc.blocks) do
    if not (b.t == "Div" and b.classes[1] == "title") then blocks[#blocks + 1] = b end
  end
  if FORMAT:match("typst") then
    local out = {}
    for _, b in ipairs(blocks) do
      if b.t == "Div" and b.classes[1] == "stanza" then
        local lines = b.content[1].content
        out[#out + 1] = pandoc.RawBlock("typst", "#stanza(" .. (#lines <= KEEP_MAX and "true" or "false") .. ")[")
        for _, line in ipairs(lines) do
          local inlines, lead = split_indent(line)
          out[#out + 1] = pandoc.RawBlock("typst", "#vl(" .. lead .. "em)[")
          out[#out + 1] = pandoc.Plain(inlines)
          out[#out + 1] = pandoc.RawBlock("typst", "]")
        end
        out[#out + 1] = pandoc.RawBlock("typst", "]")
      else
        out[#out + 1] = b
      end
    end
    doc.blocks = out
    return doc
  end
  -- EPUB: a heading is required for the contents, and it must come first or pandoc files what precedes it
  -- in a section of its own. A titled poem shows it; an untitled one gets a hidden heading named after
  -- the working title. The dedication follows it here (the PDF sets it above the title).
  local head = {}
  local title = text_of(doc.meta, "title")
  local dedication, epigraph, author = text_of(doc.meta, "dedication"), text_of(doc.meta, "epigraph"), text_of(doc.meta, "author")
  head[#head + 1] = pandoc.Header(1, {pandoc.Str(title)}, pandoc.Attr(titled(doc.meta) and "poem-title" or "poem-hidden-title", {"unnumbered"}))
  if dedication ~= "" then
    head[#head + 1] = pandoc.Div({pandoc.Para({pandoc.Str(dedication)})}, pandoc.Attr("", {"dedication"}))
  end
  if author ~= "" then
    head[#head + 1] = pandoc.Div({pandoc.Para({pandoc.Str(author)})}, pandoc.Attr("", {"byline"}))
  end
  if epigraph ~= "" then
    head[#head + 1] = pandoc.Div({pandoc.Para({pandoc.Str(epigraph)})}, pandoc.Attr("", {"epigraph"}))
  end
  for _, b in ipairs(blocks) do head[#head + 1] = b end
  doc.blocks = head
  return doc
end
````

Create `plugins/wrist/skills/wrist/publish/poem/poem.typ`:

````typst
// wrist poem template for `pandoc --pdf-engine=typst`. A5 (or the trim size), flush left, never justified.
// Needs typst 0.12 or later.
#set document(title: [$title$])
#set text(
  font: ($if(mainfont)$"$mainfont$", $endif$"Libertinus Serif", "DejaVu Serif"),
  size: 11pt,
  lang: "$if(lang)$$lang$$else$en$endif$",
)
#set par(justify: false, leading: 0.55em, spacing: 0.55em)
#set page(
  paper: "$if(papersize)$$papersize$$else$a5$endif$",
  margin: (x: 2.2cm, y: 2.4cm),
  numbering: none,
  footer: context {
    if counter(page).get().first() > 1 { align(center)[#counter(page).display("1")] }
  },
)

#let stanza(keep, body) = block(breakable: not keep, above: 0pt, below: 1.4em, width: 100%)[#body]
#let vl(lead, body) = block(above: 0pt, below: 0.55em, width: 100%)[#par(hanging-indent: lead + 1.5em)[#h(lead)#body]]

$if(dedication)$
#align(right)[#emph[$dedication$]]
#v(2em)
$endif$
$if(titled)$
#block(below: 0.6em)[#text(weight: "bold", size: 1.3em)[$title$]]
$endif$
$if(author)$
#block(below: 1.6em)[#emph[$for(author)$$author$$sep$, $endfor$]]
$endif$
$if(epigraph)$
#block(below: 1.8em, inset: (left: 1.5em))[#emph[$epigraph$]]
$endif$

$body$
````

Create `plugins/wrist/skills/wrist/publish/poem/poem.css`:

````css
body { font-family: "Libertinus Serif", Georgia, serif; line-height: 1.5; margin: 0 10%; }
.line-block { margin: 0 0 1.4em 0; }
div.stanza { page-break-inside: avoid; }
div.dedication { text-align: right; font-style: italic; margin-bottom: 2em; }
div.byline { font-style: italic; margin-bottom: 1.6em; }
div.epigraph { font-style: italic; margin: 0 0 1.8em 1.5em; }
#poem-title > h1 { font-size: 1.3em; margin-bottom: 0.4em; }
#poem-hidden-title > h1 { display: none; }
````

- [ ] **Step 5: Run the tests**

Run: `python3 -m unittest discover -s plugins/wrist/tests -p "test_poem_publish.py" -q 2>&1 | tail -4`
Expected: `Ran 5 tests` and `OK`.

- [ ] **Step 6: Look at a built page**

Build the prototype poem to see the layout (the example arrives in Task 9, so use a scratch file):

```bash
S=/tmp/claude-1000/-home-sean-Data-Projects-claude-plugins/b823c3ae-57a6-454b-b3b3-63ef3fa1a7f8/scratchpad
mkdir -p $S/layout && cd $S/layout
printf '# Counting Down\n\nI do not count the stairs,\n    the way you said I should\n        and a very long line that keeps going well past the margin of an A5 page so that it must wrap around\n\nbecause the gap is where I live.\n' > q.md
D=/home/sean/Data/Projects/claude-plugins/plugins/wrist/skills/wrist/publish/poem
pandoc --from $D/verse.lua q.md --lua-filter $D/poem.lua --template $D/poem.typ --pdf-engine=typst -M title="Counting Down" -M author="Ada Example" -M titled=true -M epigraph="for the stairs" -M dedication="for M." -o q.pdf
$S/venv/bin/python -c "import pymupdf; d=pymupdf.open('q.pdf'); print(len(d)); d[0].get_pixmap(dpi=80).save('q1.png')"
```

Read `q1.png`. Expected: one page; the dedication in italic at the top right; the title in bold, the byline and the epigraph in italic; the first line at the margin; the second indented about 2 ems; the third indented 4 ems, its wrapped continuation indented further (a hanging indent) and never flush with the margin; a space between the stanzas; no page number on a one-page poem.

- [ ] **Step 7: Run the whole suite and commit**

Run: `python3 -m unittest discover -s plugins/wrist/tests -q 2>&1 | tail -3`
Expected: `OK`.

```bash
git add plugins/wrist/skills/wrist/scripts/wrist_publish.py plugins/wrist/skills/wrist/scripts/wrist_check.py plugins/wrist/skills/wrist/publish/poem plugins/wrist/tests/test_poem_publish.py
git commit -m "feat(wrist): publish a poem as set verse" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01BbGUbm5dYKZovMogE1FAjn"
```

---


### Task 9: The `verse` command, the gate, and the example villanelle

**Files:**
- Modify: `plugins/wrist/skills/wrist/scripts/wrist_check.py`, `plugins/wrist/tests/support.py`
- Create: `plugins/wrist/skills/wrist/assets/examples/counting/` (five files and the stamps the `stamp` command writes), `plugins/wrist/tests/test_poem.py`

**Interfaces:**
- Consumes: `Profile.form_paths`, `wrist_verse` (all of it), `top_section`, `field_text`, `read_text`, `load_all`, `project_root`.
- Produces in `wrist_check`: `forms_dir(profile)`, `verse_problems(files, profile, pm, slug, root) -> list[(severity, file, line, message)]` (severity `error` or `estimate`), the `verse` command (`verse WRIST_DIR [--root .] [--json]`; lines `file:line: error|estimate: message`, then `N errors, M estimates (estimates are advisory and never block)`; exit 1 on any error; exits with `profile '<name>' has no poem form` for a profile without `form`), and in `gate_blockers` for `publishing` every `error` from `verse_problems` as `<file>:<line>: <message>` when the profile has a `form`.
- `verse_problems` order: a missing skeleton ends the run; the skeleton is parsed (a `ParseError` is one error with `column N:`), its rules, the structure stand-in's `Form:`, `Lines:` and `Stanzas:`, the `named` catalog form; a missing poem is one error; a skeleton with rule errors leaves the poem unchecked (one error saying so); then the exact checks and the estimates.
- In `support.py`: `POEM_EXAMPLE`, `P_PREMISE`, `P_STRUCTURE`, `P_POEM`, class `PoemCase`.
- The example (`counting`, a titled villanelle, 19 lines): passes `check`, `verse` (0 errors, 0 estimates), the publishing gate and `lint` (0 hits), and builds.

- [ ] **Step 1: Add the test support and write the failing tests**

Apply this patch to `plugins/wrist/tests/support.py` (write it to `/tmp/support.patch`, then `git apply /tmp/support.patch`):

````diff
--- a/plugins/wrist/tests/support.py
+++ b/plugins/wrist/tests/support.py
@@ -39,6 +39,10 @@
 S_ACT1 = "wrist/work/act-1.md.wrist.md"
 S_ACT2 = "wrist/work/act-2.md.wrist.md"
 S_ACT3 = "wrist/work/act-3.md.wrist.md"
+POEM_EXAMPLE = os.path.join(SKILL, "assets", "examples", "counting")
+P_PREMISE = "wrist/PREMISE.md"
+P_STRUCTURE = "wrist/structure.md.wrist.md"
+P_POEM = "wrist/work/counting.md.wrist.md"
 NO_UNKNOWNS = "- **Unknowns:** none\n"
 
 
@@ -95,3 +99,7 @@
 
 class ScriptCase(TreeCase):
     example = SCRIPT_EXAMPLE
+
+
+class PoemCase(TreeCase):
+    example = POEM_EXAMPLE
````

Create `plugins/wrist/tests/test_poem.py`:

````python
import json
import os
import re
import shutil
import unittest
import zipfile

from support import P_POEM, P_PREMISE, P_STRUCTURE, PoemCase

import wrist_verse

HAVE_TOOLS = shutil.which("pandoc") and shutil.which("typst")


class Example(PoemCase):
    def test_the_example_passes_check_verse_and_the_gate(self):
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("0 errors", out)
        code, out = self.run_wrist("verse", "wrist", "--root", ".")
        self.assertEqual(code, 0, out)
        self.assertIn("0 errors, 0 estimates", out)
        code, out = self.run_wrist("gate", "wrist", "publishing", "--root", ".")
        self.assertEqual(code, 0, out)
        self.assertIn("open", out)

    def test_the_example_is_clean_under_lint(self):
        code, out = self.run_wrist("lint", "wrist", "--root", ".")
        self.assertEqual(code, 0, out)
        self.assertIn("0 hits in 0 files", out)

    def test_the_example_is_a_real_villanelle(self):
        poem = wrist_verse.parse_poem(self.read("structure.md"))
        self.assertEqual(poem.named, "villanelle")
        self.assertEqual(wrist_verse.total_lines(poem), 19)


class VerseCommand(PoemCase):
    def verse(self, *extra):
        return self.run_wrist("verse", "wrist", "--root", ".", *extra)

    def test_a_changed_refrain_is_an_error_and_blocks_the_gate(self):
        self.replace("work/counting.md", "Some lids have rusted shut. I never find,\nthe same count twice. I stoop. The light is low.\nI count the jars my mother left behind.",
                     "Some lids have rusted shut. I never find,\nthe same count twice. I stoop. The light is low.\nI count the jars my mother left ahead.")
        code, out = self.verse()
        self.assertEqual(code, 1, out)
        self.assertIn("work/counting.md:9: error: R8: line 6 must repeat line 1 (refrain R1) word for word", out)
        self.run_wrist("stamp", "wrist", "work/counting.md", "--root", ".")
        code, out = self.run_wrist("gate", "wrist", "publishing", "--root", ".")
        self.assertEqual(code, 1, out)
        self.assertIn("work/counting.md:9: R8: line 6 must repeat line 1", out)

    def test_estimates_never_fail_the_command_or_the_gate(self):
        self.replace("work/counting.md", "forty in the cellar's dark, row on row,", "forty in the dark, row on row,")
        code, out = self.verse()
        self.assertEqual(code, 0, out)
        self.assertIn("estimate: about 8 syllables, the skeleton asks for 10 to 11 (estimate)", out)
        self.assertIn("0 errors, 1 estimates", out)
        self.run_wrist("stamp", "wrist", "work/counting.md", "--root", ".")
        code, out = self.run_wrist("gate", "wrist", "publishing", "--root", ".")
        self.assertEqual(code, 0, out)

    def test_a_syntax_error_in_the_skeleton_names_line_and_column(self):
        self.replace("structure.md", "refrain R1 at 1, 6, 12, 18;", "refrain R1 at 1, 6, 12, 18")
        code, out = self.verse()
        self.assertEqual(code, 1, out)
        self.assertRegex(out, r"structure\.md:4: error: column \d+: expected ';', found 'refrain'")

    def test_a_skeleton_rule_failure(self):
        self.replace("structure.md", "refrain R2 at 3, 9, 15, 19;", "refrain R2 at 3, 9, 15, 29;")
        code, out = self.verse()
        self.assertEqual(code, 1, out)
        self.assertIn("structure.md:4: error: R8: refrain R2: line 29 is outside the poem (it has 19 lines)", out)

    def test_the_stand_in_must_agree_with_the_skeleton(self):
        self.replace(P_STRUCTURE, "- **Form:** villanelle", "- **Form:** sestina")
        self.replace(P_STRUCTURE, "- **Lines:** 19", "- **Lines:** 20")
        self.replace(P_STRUCTURE, "- **Stanzas:** 6", "- **Stanzas:** 5")
        code, out = self.verse()
        self.assertEqual(code, 1, out)
        self.assertIn("`Form:` says 'sestina' but structure.md says 'villanelle'", out)
        self.assertIn("`Lines:` says 20 but structure.md has 19", out)
        self.assertIn("`Stanzas:` says 5 but structure.md has 6", out)

    def test_a_form_that_is_not_in_the_catalog(self):
        self.replace("structure.md", 'named "villanelle"', 'named "sapphic"')
        code, out = self.verse()
        self.assertEqual(code, 1, out)
        self.assertIn("named form 'sapphic' is not in the catalog (ballad, blank-verse", out)

    def test_a_skeleton_that_departs_from_its_named_form(self):
        self.replace("structure.md", "refrain R2 at 3, 9, 15, 19;\n", "")
        code, out = self.verse()
        self.assertEqual(code, 1, out)
        self.assertIn("named form villanelle: the refrains differ", out)

    def test_the_title_line_must_match_titled(self):
        self.replace(P_PREMISE, "titled: yes", "titled: no")
        code, out = self.verse()
        self.assertEqual(code, 1, out)
        self.assertIn("the poem has a title line but PREMISE.md says `titled: no`", out)

    def test_json_output(self):
        self.replace("work/counting.md", "forty in the cellar's dark, row on row,", "forty in the dark, row on row,")
        code, out = self.verse("--json")
        self.assertEqual(code, 0, out)
        data = json.loads(out)
        self.assertEqual([(d["severity"], d["file"], d["line"]) for d in data], [("estimate", "work/counting.md", 4)])

    def test_a_missing_poem_is_reported_and_the_skeleton_is_still_checked(self):
        os.remove(self.path("work/counting.md"))
        code, out = self.verse()
        self.assertEqual(code, 1, out)
        self.assertIn("work/counting.md:1: error: the file does not exist yet; realize it first", out)
        self.assertIn("1 errors, 0 estimates", out)
        self.replace("structure.md", "refrain R2 at 3, 9, 15, 19;", "refrain R2 at 3, 9, 15, 29;")
        code, out = self.verse()
        self.assertIn("structure.md:4: error: R8: refrain R2: line 29 is outside the poem", out)
        self.assertIn("work/counting.md:1: error: the file does not exist yet", out)

    def test_a_missing_skeleton_is_reported(self):
        os.remove(self.path("structure.md"))
        code, out = self.verse()
        self.assertEqual(code, 1, out)
        self.assertIn("structure.md:1: error: the file does not exist yet; realize it first", out)

    def test_a_skeleton_with_rule_errors_leaves_the_poem_unchecked(self):
        self.replace("structure.md", "refrain R2 at 3, 9, 15, 19;", "refrain R2 at 3, 9, 15, 29;")
        code, out = self.verse()
        self.assertIn("work/counting.md:1: error: the poem was not checked: fix the errors in structure.md first", out)

    def test_a_profile_without_a_form_refuses(self):
        code, out = self.run_wrist("verse", "wrist", "--profile", "shortstory", "--root", ".")
        self.assertNotEqual(code, 0)
        self.assertIn("has no poem form", out)


@unittest.skipUnless(HAVE_TOOLS, "pandoc and typst are not installed")
class RealBuild(PoemCase):
    def publish(self):
        code, out = self.run_wrist("publish", "wrist", "--root", ".")
        self.assertEqual(code, 0, out)
        self.assertIn("published output/counting.epub and output/counting.pdf", out)

    def epub(self, name):
        with zipfile.ZipFile(self.path("output/counting.epub")) as z:
            return z.read(name).decode("utf-8")

    def test_a_titled_poem_builds_a_pdf_and_an_epub_with_one_contents_entry(self):
        self.publish()
        with open(self.path("output/counting.pdf"), "rb") as fh:
            self.assertEqual(fh.read(5), b"%PDF-")
        nav = self.epub("EPUB/nav.xhtml")
        self.assertEqual(re.findall(r"<a [^>]*>([^<]*)</a>", nav), ["Counting"])
        self.assertIn('id="poem-title"', self.epub("EPUB/text/ch001.xhtml"))
        self.assertEqual(len([n for n in zipfile.ZipFile(self.path("output/counting.epub")).namelist() if n.endswith(".xhtml")]), 2)

    def test_the_epub_keeps_every_line_and_stanza(self):
        self.publish()
        page = self.epub("EPUB/text/ch001.xhtml")
        self.assertEqual(page.count('<div class="stanza">'), 6)
        self.assertIn("I count the jars my mother left behind,<br />", page)
        self.assertIn("for my mother", page)

    def test_an_untitled_poem_hides_its_working_title_in_the_epub(self):
        self.replace(P_PREMISE, "titled: yes", "titled: no")
        self.write("work/counting.md", self.read("work/counting.md").split("\n", 2)[2])
        self.run_wrist("stamp", "wrist", "work/counting.md", "--root", ".")
        self.publish()
        self.assertIn('id="poem-hidden-title"', self.epub("EPUB/text/ch001.xhtml"))
        self.assertIn("poem-hidden-title > h1", self.epub("EPUB/styles/stylesheet1.css"))

    def test_special_characters_in_the_title_and_epigraph_build(self):
        self.replace(P_PREMISE, "title: Counting", 'title: A & B #1 @home "Q"')
        self.replace(P_PREMISE, "dedication: for my mother", 'dedication: for M. & $5 @x')
        self.replace("work/counting.md", "# Counting", '# A & B #1 @home "Q"')
        self.run_wrist("stamp", "wrist", "work/counting.md", "--root", ".")
        self.publish()
        self.assertIn("A &amp; B #1 @home", self.epub("EPUB/text/ch001.xhtml"))
````

- [ ] **Step 2: Run them to see them fail**

Run: `python3 -m unittest discover -s plugins/wrist/tests -p "test_poem.py" -q 2>&1 | tail -4`
Expected: errors (`FileNotFoundError` for the example folder).

- [ ] **Step 3: Write the example**

Create `plugins/wrist/skills/wrist/assets/examples/counting/wrist/PREMISE.md`:

````markdown
---
profile: poem
title: Counting
slug: counting
author: Ada Example
language: en
titled: yes
dedication: for my mother
questions_generation: done
questions_realization: done
questions_publishing: done
review_done: yes
---

# Premise

A worked example: a nineteen-line villanelle about a cellar full of preserves.

## Answers

- **subject:** A woman counts her late mother's preserving jars in a dark cellar, and the count never comes out the same.
- **form:** villanelle
- **tone:** Dry and plain, tightening toward the end; no grief named.
- **audience:** Adult readers of a literary magazine.
- **length:** The form's own: nineteen lines.
- **speaker:** The daughter, alone, speaking to no one.
- **occasion:** none (skipped on purpose)
- **rhyme:** Strict on the villanelle's two sounds.
- **images:** The jars, the pencilled labels, the cellar stairs, the bulb that gave out.
- **avoid:** The word "grief"; any jar that turns out to be special.
- **titled:** yes
- **epigraph:** none (skipped on purpose)
- **dedication:** For my mother.
- **keep:** The stairs come out one short, and nothing explains it.
````

Create `plugins/wrist/skills/wrist/assets/examples/counting/wrist/structure.md.wrist.md`:

````markdown
# structure: Counting

Notes for the skeleton of the poem.

- **Form:** villanelle
- **Lines:** 19
- **Stanzas:** 6
- **Rhyme:** A for the -ind sound (behind, unkind, find, mind, blind, unwind, kind), B for the -ow sound (row, low, know, below, shows, slow).
- **Meter:** Iambic pentameter, with a tenth or eleventh syllable allowed.
- **Rules:** The two refrains keep their words; the turn is the change of meaning, not a change of line.
- **Required:** always
- **Depends on:** none
- **Referred by:** [counting](./work/counting.md.wrist.md)
- **Unknowns:** none
````

Create `plugins/wrist/skills/wrist/assets/examples/counting/wrist/work/counting.md.wrist.md`:

````markdown
# poem: Counting

Notes for the poem itself.

- **Subject:** A daughter counting her mother's preserving jars in the cellar, and the count that never agrees.
- **Speaker:** The daughter, alone.
- **Tone:** Dry and plain; the feeling stays in the objects.
- **Turn:** At the fourth tercet: the dark and the stairs, then the stairs themselves come out one short.
- **Ending:** She leaves one jar uncounted and goes up slowly; the refrains return unchanged in words and changed in meaning.
- **Must include:** The pencilled label, the bulb that gave out, the stairs one short.
- **Must avoid:** The word grief; any explanation of the missing step.
- **Must keep:** The stairs come out one short.
- **Rules:** No simile. End on the refrain.
- **Required:** always
- **Depends on:** [structure](../structure.md.wrist.md) (realizes)
- **Referred by:** none
- **Unknowns:** none
````

Create `plugins/wrist/skills/wrist/assets/examples/counting/structure.md`:

````text
poem {
  named "villanelle";
  refrain R1 at 1, 6, 12, 18;
  refrain R2 at 3, 9, 15, 19;
  stanza (tercet, 5, A B A) {
    line (iamb 5, stop, A) { image["the jars left in the cellar"] }
    line (iamb 5, stop, B) { image["their number, the dark, the rows"] }
    line (iamb 5, stop, A) { image["the pencilled label, steady and cold"] }
  }
  stanza (quatrain, 1, A B A A) {
    line (iamb 5, stop, A) { action["leaving one jar uncounted"] }
    line (iamb 5, stop, B) { action["going up the stairs slowly"] }
    line (iamb 5, stop, A) { }
    line (iamb 5, stop, A) { }
  }
}
````

Create `plugins/wrist/skills/wrist/assets/examples/counting/work/counting.md`:

````text
# Counting

I count the jars my mother left behind,
forty in the cellar's dark, row on row,
the label's hand is steady and unkind.

Some lids have rusted shut. I never find,
the same count twice. I stoop. The light is low.
I count the jars my mother left behind.

Thirty-nine, then forty. And do I mind?
Which jar is gone? Nobody else would know.
The label's hand is steady and unkind.

The bulb gave out last spring. I climb half blind,
one hand along the wall, the stairs below.
I count the jars my mother left behind,

and each step down I count, and so unwind.
The stairs come out one short, and nothing shows.
The label's hand is steady and unkind.

One jar I leave uncounted, to be kind,
since she would have counted. Let her. I go slow.
I count the jars my mother left behind.
The label's hand is steady and unkind.
````

- [ ] **Step 4: Apply the `verse` command and the gate**

`/tmp/check2.patch`:

````diff
--- a/plugins/wrist/skills/wrist/scripts/wrist_check.py
+++ b/plugins/wrist/skills/wrist/scripts/wrist_check.py
@@ -13,6 +13,7 @@
   fix-backlinks    insert missing `Referred by:` lines (dry-run by default)
   gate PHASE       list what blocks the generation, realization or publishing phase
   lint             scan realized prose for the profile's clichés (advisory)
+  verse            check a poem against its skeleton (poem profiles): exact errors, advisory estimates
   publish          build output/<slug>.epub and output/<slug>.pdf
 
 Standard library only. Exit code 1 if `check` finds errors.
@@ -31,6 +32,7 @@
 import wrist_lint
 import wrist_profile
 import wrist_publish
+import wrist_verse
 
 WRIST_SUFFIX = ".wrist.md"
 PREMISE_FILE = "PREMISE.md"
@@ -1134,6 +1136,9 @@
             with open(impl, encoding="utf-8", errors="replace") as fh:
                 if not fh.read().split():
                     blockers.append(f"{path} is empty; there is nothing to publish")
+    if profile.form:
+        blockers.extend(f"{rel}:{line}: {message}" for severity, rel, line, message
+                        in verse_problems(files, profile, pm, slug, root) if severity == "error")
     if pm.front.get("review_done", (0, ""))[1].lower() != "yes":
         blockers.append(f"the review pass is not recorded; do it, then set `review_done: yes` in {PREMISE_FILE}")
     if not pm.front.get("author", (0, ""))[1]:
@@ -1183,6 +1188,81 @@
     return 0
 
 
+def forms_dir(profile):
+    return os.path.join(profile.directory, "forms")
+
+
+def verse_problems(files, profile, pm, slug, root):
+    """[(severity, file, line, message)] for a poem profile: the skeleton's own rules, its agreement with the
+    structure stand-in and with the catalog form it names, then the poem against the skeleton. Severity is
+    `error` or `estimate`."""
+    structure_rel, poem_rel = profile.form_paths(slug)
+    out = []
+
+    def add(rel, problems):
+        out.extend((p.severity, rel, p.line, p.message) for p in problems)
+
+    paths = {rel: os.path.join(root, rel) for rel in (structure_rel, poem_rel)}
+    if not os.path.isfile(paths[structure_rel]):
+        return [("error", structure_rel, 1, "the file does not exist yet; realize it first")]
+    try:
+        poem = wrist_verse.parse_poem(read_text(paths[structure_rel], "utf-8-sig"))
+    except wrist_verse.ParseError as exc:
+        return [("error", structure_rel, exc.line, f"column {exc.col}: {exc.message}")]
+    rules = wrist_verse.skeleton_problems(poem)
+    add(structure_rel, rules)
+    stand_in = next((sf for sf in files.values() if sf.impl_rel == structure_rel), None)
+    top = top_section(stand_in) if stand_in else None
+    if top is not None:
+        want_form = poem.named or "custom"
+        have = field_text(stand_in, top, "Form").strip("` ")
+        if have and have != want_form:
+            out.append(("error", stand_in.rel, 1, f"`Form:` says '{have}' but {structure_rel} says '{want_form}'"))
+        for label, actual in (("Lines", wrist_verse.total_lines(poem)), ("Stanzas", wrist_verse.stanza_count(poem))):
+            m = re.match(r"\d+", field_text(stand_in, top, label))
+            if m and int(m.group()) != actual:
+                out.append(("error", stand_in.rel, 1, f"`{label}:` says {m.group()} but {structure_rel} has {actual}"))
+    if poem.named:
+        catalog = wrist_verse.load_catalog(poem.named, forms_dir(profile))
+        if catalog is None:
+            known = ", ".join(wrist_verse.list_catalog(forms_dir(profile)))
+            out.append(("error", structure_rel, 1, f"named form '{poem.named}' is not in the catalog ({known})"))
+        else:
+            add(structure_rel, wrist_verse.catalog_problems(poem, catalog, poem.named))
+    if not os.path.isfile(paths[poem_rel]):
+        out.append(("error", poem_rel, 1, "the file does not exist yet; realize it first"))
+        return out
+    if any(p.severity == "error" for p in rules):
+        out.append(("error", poem_rel, 1, f"the poem was not checked: fix the errors in {structure_rel} first"))
+        return out
+    verse = wrist_verse.read_verse(read_text(paths[poem_rel], "utf-8-sig"))
+    titled = bool(profile.options.get("titled"))
+    add(poem_rel, wrist_verse.poem_problems(poem, verse, titled, pm.front.get("title", (0, ""))[1]))
+    add(poem_rel, wrist_verse.estimates(poem, verse))
+    return out
+
+
+def setup_verse(p):
+    p.add_argument("--root")
+    p.add_argument("--json", action="store_true")
+
+
+@command("verse", setup_verse)
+def cmd_verse(args):
+    wrist_root, files, profile, pm, slug = load_all(args)
+    if not profile.form:
+        sys.exit(f"profile '{profile.name}' has no poem form; `verse` is for poem profiles")
+    found = verse_problems(files, profile, pm, slug, project_root(args))
+    if args.json:
+        print(json.dumps([{"severity": s, "file": f, "line": ln, "message": m} for s, f, ln, m in found], indent=1))
+    else:
+        for severity, rel, line, message in sorted(found, key=lambda r: (r[0] != "error", r[1], r[2])):
+            print(f"{rel}:{line}: {severity}: {message}")
+        errors = sum(1 for r in found if r[0] == "error")
+        print(f"\n{errors} errors, {len(found) - errors} estimates (estimates are advisory and never block)")
+    return 1 if any(r[0] == "error" for r in found) else 0
+
+
 PUBLISH_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "publish"))
 
 
````

Run: `git apply /tmp/check2.patch && git diff --stat`

Then stamp the example (this writes `wrist/.stamps`) and look at it:

```bash
cd plugins/wrist/skills/wrist/assets/examples/counting
S=../../../scripts/wrist_check.py
python3 $S stamp wrist structure.md work/counting.md --root .
python3 $S check wrist | tail -1
python3 $S verse wrist --root .
python3 $S gate wrist publishing --root .
python3 $S lint wrist --root . | grep hits
cd -
```

Expected: `2 stamped`; `2 stand-ins, 1 dependency edges, 0 unknowns; 0 errors, 0 warnings`; `0 errors, 0 estimates (estimates are advisory and never block)`; `gate publishing: open`; `0 hits in 0 files`.

- [ ] **Step 5: Run the tests and the whole suite**

Run: `python3 -m unittest discover -s plugins/wrist/tests -p "test_poem.py" -q 2>&1 | tail -4`
Expected: `Ran 20 tests` and `OK`.

Run: `python3 -m unittest discover -s plugins/wrist/tests -q 2>&1 | tail -3`
Expected: `OK`.

Also run `git status --short plugins/wrist/skills/wrist/assets/examples/counting`: it must not list an `output/` folder (the real-build tests build inside a temporary copy).

- [ ] **Step 6: Look at the example's pages**

```bash
S=/tmp/claude-1000/-home-sean-Data-Projects-claude-plugins/b823c3ae-57a6-454b-b3b3-63ef3fa1a7f8/scratchpad
rm -rf $S/cview && cp -r plugins/wrist/skills/wrist/assets/examples/counting $S/cview && cd $S/cview
python3 /home/sean/Data/Projects/claude-plugins/plugins/wrist/skills/wrist/scripts/wrist_check.py publish wrist --root .
$S/venv/bin/python -c "import pymupdf; d=pymupdf.open('output/counting.pdf'); print(len(d)); d[0].get_pixmap(dpi=80).save('c1.png')"
unzip -p output/counting.epub EPUB/nav.xhtml | grep -o "<a [^>]*>[^<]*"
cd /home/sean/Data/Projects/claude-plugins
```

Read `c1.png`. Expected: one A5 page; "for my mother" in italic at the top right, then **Counting**, the byline "Ada Example", six stanzas (five tercets and a quatrain) with the refrains word for word, no page number. The contents list one entry, "Counting".

- [ ] **Step 7: Commit**

```bash
git add plugins/wrist/skills/wrist/scripts/wrist_check.py plugins/wrist/skills/wrist/assets/examples/counting plugins/wrist/tests/support.py plugins/wrist/tests/test_poem.py
git commit -m "feat(wrist): add the verse command, the publishing gate checks and the counting example" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01BbGUbm5dYKZovMogE1FAjn"
```

---


### Task 10: Skill, references and templates

**Files:**
- Modify: `plugins/wrist/skills/wrist/SKILL.md`, `plugins/wrist/skills/wrist/references/grammar.md`, `plugins/wrist/skills/wrist/references/publishing.md`, `README.md`, `plugins/wrist/.claude-plugin/plugin.json`, `plugins/wrist/tests/test_docs.py`
- Create: `plugins/wrist/skills/wrist/references/psg.md`, `plugins/wrist/skills/wrist/references/verse.md`, `plugins/wrist/skills/wrist/assets/templates/poem/{PREMISE.md,structure.wrist.md,poem.wrist.md,skeleton.md}`

- [ ] **Step 1: Write the failing doc tests**

Save this as `/tmp/test_docs_edit.py` and run `python3 /tmp/test_docs_edit.py plugins/wrist/tests/test_docs.py`; each replacement asserts its anchor exists once.

````python
import sys
p = sys.argv[1]
s = open(p, encoding="utf-8").read()
def rep(old, new):
    global s
    assert s.count(old) == 1, old[:70]
    s = s.replace(old, new)
rep('COMMANDS = ("check", "unknowns", "order", "status", "stamp", "fix-backlinks", "gate", "lint", "publish")',
    'COMMANDS = ("check", "unknowns", "order", "status", "stamp", "fix-backlinks", "gate", "lint", "verse", "publish")')
rep('''    def test_the_readme_lists_the_screenplay(self):
        self.assertIn("`shortstory`, `novel` and `screenplay`", text(ROOT, "README.md"))
''','''    def test_the_readme_lists_the_four_profiles(self):
        self.assertIn("`shortstory`, `novel`, `screenplay` and `poem` exist", text(ROOT, "README.md"))

    def test_skill_covers_the_poem(self):
        skill = text(SKILL, "SKILL.md")
        for phrase in ("`poem`", "references/psg.md", "references/verse.md", "assets/templates/poem/", "titled:",
                       "profiles/poem/forms/", "revise the line, not the skeleton", "deleting the last line",
                       "Four profiles exist"):
            self.assertIn(phrase, skill, phrase)
        self.assertNotIn("not built yet", skill)

    def test_every_poem_template_exists_and_the_skeleton_template_is_valid(self):
        import wrist_verse
        for name in ("PREMISE.md", "structure.wrist.md", "poem.wrist.md", "skeleton.md"):
            self.assertTrue(os.path.isfile(os.path.join(SKILL, "assets", "templates", "poem", name)), name)
        poem = wrist_verse.parse_poem(text(SKILL, "assets", "templates", "poem", "skeleton.md"))
        self.assertEqual(wrist_verse.skeleton_problems(poem), [])

    def test_the_grammar_reference_explains_the_form_setting(self):
        grammar = text(SKILL, "references", "grammar.md")
        for phrase in ("`form`", "psg.md", "verse.md", "`poem`"):
            self.assertIn(phrase, grammar, phrase)

    def test_the_psg_reference_covers_the_grammar_and_every_rule(self):
        ref = text(SKILL, "references", "psg.md")
        for phrase in ["refrain NAME at", "ends @list[k]", "fresh", "strict roles", "breaks flexible", "named",
                       "syllables", "stress", "## What changed from PSGv2"] + [f"**R{n} " for n in range(13)]:
            self.assertIn(phrase, ref, phrase)

    def test_the_verse_reference_covers_the_format_and_the_command(self):
        ref = text(SKILL, "references", "verse.md")
        for phrase in ("titled: yes", "# Title", "half an em", "wrist_check.py verse", "estimate", "gate publishing"):
            self.assertIn(phrase, ref, phrase)

    def test_the_publishing_reference_describes_a_poem(self):
        self.assertIn("## A poem", text(SKILL, "references", "publishing.md"))
''')
open(p, "w", encoding="utf-8").write(s)
````

Run: `python3 -m unittest discover -s plugins/wrist/tests -p "test_docs.py" -q 2>&1 | tail -4`
Expected: failures for the new doc tests (the references, templates and skill text do not exist yet).

- [ ] **Step 2: Write the references**

Create `plugins/wrist/skills/wrist/references/psg.md`:

````markdown
# The poem grammar: PSGv2.1

`structure.md` is a **skeleton**: a document in this grammar that fixes a poem's form, its rhetorical shape and the
kind of material each slot holds, before any verse is written. It is PSGv2 (the poem skeleton grammar) with its
defects repaired; the changes are listed at the end. `wrist_check.py verse` parses it, checks the rules below and
checks the poem against it. The standard forms are ready-made skeletons in `profiles/poem/forms/`: copy one, keep
its `named "<form>";` line, and add what the poem needs. Write `custom` in the stand-in's `Form:` for a skeleton
of your own.

## Syntax

Terminals are in double quotes. `?` optional, `+` one or more, `*` zero or more, `|` alternatives. White space between
tokens is insignificant. Comments are `(* ... *)`.

```text
Poem      ::= "poem" "{" Decl* Stanza+ "}"
Decl      ::= Named | Title | Strict | Breaks | Rule | Refrain
Named     ::= "named" String ";"                  (* the catalog form this skeleton follows *)
Title     ::= "title" String ";"                  (* informational; ignored by the checker *)
Strict    ::= "strict" "roles" ";"                (* turn on the role rules R3 to R5 *)
Breaks    ::= "breaks" "flexible" ";"             (* the stanza division is not compared to the catalog form *)
Rule      ::= "let" Identifier "=" Value ";"
Value     ::= String | "[" (String ("," String)*)? "]"
Refrain   ::= "refrain" Identifier "at" Integer ("," Integer)+ ";"

Stanza    ::= "stanza" "(" Shape "," Count "," Rhyme ("," Role)? ")" "{" Line+ "}"
Shape     ::= "couplet" | "tercet" | "quatrain" | "quintain" | "sestet" | "septet" | "octave" | "free"
Count     ::= Integer (".." (Integer | "*"))?
Rhyme     ::= "none" | "fresh"? Tag+
Role      ::= "setup" | "develop" | "turn" | "resolve"

Line      ::= "line" "(" Meter "," Ending ("," "caesura" Integer)? "," Tag ("," "ends" Word)? ")" "{" Unit* "}"
Meter     ::= Foot Integer | "syllables" Integer (".." Integer)? | "free" | "stress" String
Foot      ::= "iamb" | "trochee" | "anapest" | "dactyl" | "spondee" | "amphibrach"
Ending    ::= "stop" | "run"
Tag       ::= "A" | "B" | ... | "Z" | "x"
Word      ::= "@" Identifier "[" Integer "]"

Unit      ::= Kind "[" String "]" ";"?
Kind      ::= "image" | "action" | "statement" | "pivot" | "question" | "address"
String    ::= '"' character* '"'                  (* a double quote inside is written \" *)
Identifier ::= letter (letter | digit | "_")*
Integer   ::= digit+
```

## What the pieces mean

| Piece | Meaning |
|---|---|
| `Shape` | The number of lines in the stanza: couplet 2, tercet 3, quatrain 4, quintain 5, sestet 6, septet 7, octave 8, `free` at least 1. |
| `Count` | How many times the stanza repeats: `3` exactly three; `2..5` two to five; `2..*` two or more. In `structure.md` the count is exact (R11); ranges belong to catalog entries. |
| `Rhyme` | One tag per line, in order. `none` means every line is `x`. Tags are poem-wide sound classes: lines sharing a tag rhyme, across stanzas. `x` is unrhymed. `fresh` renames the tags in each repeat, so every repeated stanza has its own sounds. |
| `Meter` | `iamb 5` is iambic pentameter (a foot name and a number of feet); `syllables 5` or `syllables 7..9` counts syllables; `free` fixes nothing; `stress "1010"` gives a pattern of stressed (1) and unstressed (0) syllables. Meter is a target: the checker only estimates it. |
| `Ending` | `stop` ends at a syntactic pause; `run` runs on (enjambment). |
| `caesura N` | A pause after the N-th foot, counting from 1, for foot meters. |
| `ends @list[k]` | The line's last word is exactly item k (counting from 0) of the `let` list. This is how a sestina's end words are fixed. |
| `refrain NAME at P1, P2, ...;` | The lines at these positions (counted from 1 in the whole poem) are the same line, word for word. The first position holds the units. All positions must have the same meter, ending and tag. A line is in at most one refrain. |
| `let` | A named string or list, referred to in hints as `@name` or `@name[k]`, and by `ends`. `@name[$n]` indexes by the stanza's repeat number, modulo the length of the list. |
| `named "form"` | The skeleton follows that catalog form; `verse` reports every difference (line count, rhyme scheme up to renaming letters, refrain positions, `ends` pattern, meter, and unless `breaks flexible;` the stanza division). |
| `Unit` | A slot for content of the given kind, with a hint in your own words (3 to 10 words). Units are optional. Do not copy a hint into the poem. |

### Roles and units (planning vocabulary)

Roles say what a stanza is for: **setup** establishes the scene with concrete material and a first claim;
**develop** extends it; **turn** is the volta, reversing or reframing what came before; **resolve** is a short close.
Unit kinds, each with a test: `image` (a concrete phrase a reader could draw), `action` (a verb of the body),
`statement` (an abstract claim arising from an image earlier in the stanza), `pivot` (a reversal, with a contrastive
word or an undermining question; deleting it should change the poem), `question` (left open), `address` (a
second-person plea or command). Roles and units are accepted anywhere. They are *checked* only under `strict roles;`.

## Rules

Checked by `verse`, each reported with the line of `structure.md` it concerns. R9 and R10 are advisory.

- **R0 References.** Every `@name` in a hint or `ends` names a `let`; an `ends` index is inside the list; `$n` appears
  only in a stanza repeated more than once.
- **R1 Rhyme length.** The rhyme has one tag per line and equals the line tags; `none` means all `x`.
- **R2 Shape.** A shape's line count is exact (`free`: at least 1).
- **R3 Role patterns** (strict roles only). A stanza's units, read in order, match its role exactly:
  setup `image image (action | image) statement`; develop `(image | action)+ statement?`; turn
  `pivot (image | question) (address | image) statement`; resolve `image statement`. Every stanza needs a role, and
  the poem ends on a statement.
- **R4 One turn** (strict roles only). Exactly one stanza is the turn.
- **R5 Earned statements** (strict roles only). A statement follows an image in its own stanza.
- **R6 Tags** are poem-wide unless the stanza's rhyme is `fresh`.
- **R7 Line count.** The expanded poem has the sum of shape lines times counts.
- **R8 Refrains.** Positions are inside the poem and rise; a line is in one refrain; the lines of a refrain share
  meter, ending and tag.
- **R9 Stress** (advisory). `verse` estimates syllables against the pattern's length. It cannot estimate which
  syllables are stressed (it has no pronouncing dictionary), so the pattern itself is for you and the reader.
- **R10 Caesura** (advisory). A line with `caesura N` has a pause (comma, dash or colon) inside it.
- **R11 Concrete.** Counts in `structure.md` are exact.
- **R12 Ends.** In the poem, every line with `ends @list[k]` ends with item k of the list.

## Using it

1. Decide the form first, quickly, and do not revisit it while writing. Copy a catalog skeleton when the form is one
   of them. Decide, for a poem of your own: stanzas and counts, shapes, meter, rhyme, refrains and `let` lists, and
   (if you want them) roles with exactly one turn.
2. Write the skeleton and run `wrist_check.py verse` until the skeleton has no errors. The only error left is that
   the poem file does not exist yet.
3. Write the poem into the skeleton. If a line fails, revise the line, not the skeleton.
4. Run `verse` again. Errors must be fixed; estimates are for your judgment.

## What changed from PSGv2

`refrain ... every N` became `refrain NAME at P1, P2, ...;` (a villanelle and a pantoum could not be written);
`@list[$n + k]` arithmetic became explicit `ends @list[k]` lines (the sestina rotation was only a cyclic shift);
`fresh` was added (tags were global, so a repeated stanza could not have its own rhymes); tags run A to Z instead of
A to H; `stress` takes only `1` and `0` (the old examples used a slash); role patterns are exact and optional
(`strict roles;`); `syllables` meters and the shapes `quintain` to `octave` were added; `named` and `breaks flexible`
were added; line identifiers were dropped; ranged counts are for catalog entries only (R11); R11 and R12 are new.
````

Create `plugins/wrist/skills/wrist/references/verse.md`:

````markdown
# The verse format, the verse command and its estimates

## The poem file

The realized poem (`work/<slug>.md`) is plain verse:

- If the poem is titled (`titled: yes` in `PREMISE.md`), the first line is `# Title` and the next line is blank.
  The title must equal the `title:` in `PREMISE.md`. An untitled poem has no title line.
- A stanza is the lines between blank lines; one blank line is enough (more are ignored).
- One line of verse per line of the file. Never wrap a long line by hand: the typesetter hangs a wrapped line.
- Each leading space (a tab counts four) indents the line by half an em, so `    stepped` is indented two ems.
  Spaces inside a line collapse to one.
- Nothing is markup: `*`, `_`, `#`, `1.`, `>` and `[` are literal characters. Smart punctuation is not applied; type the
  quotes and dashes you want.

## `wrist_check.py verse WRIST_DIR [--root .] [--json]`

Reads `structure.md`, the structure stand-in and the poem. Output is one line per finding,
`file:line: error|estimate: message`, then a count. Exit 1 on any error.

Errors (exact):

- the skeleton does not parse (the message gives the line and column), or breaks a rule R0 to R12;
- the structure stand-in's `Form:`, `Lines:` or `Stanzas:` disagrees with the skeleton (`Form:` is the `named` form,
  or `custom`);
- the skeleton says `named "x"` and differs from the catalog form x;
- the poem has a title line that `titled` does not allow, or lacks one it requires, or the title differs from the
  premise title;
- the poem has a different number of stanzas, or of lines in a stanza, or in all, than the skeleton;
- a refrain's lines are not the same word for word (comparing without case, spacing, curly quotes or punctuation at
  the ends of the line);
- a line with `ends @list[k]` does not end with item k.

If the skeleton has errors the poem is not checked. `gate publishing` blocks on every error.

Estimates (advisory, always labelled, never blocking). They are rough and English only:

- syllables: a vowel-group counter, less a silent final e, es or ed. A binary foot meter (iamb, trochee, spondee)
  expects the feet times 2, one more allowed (a feminine ending); a ternary one (anapest, dactyl, amphibrach) the
  feet times 3, from two fewer to one more; `syllables N..M` expects that range; a `stress` pattern expects its
  length;
- a `stop` line with no punctuation at the end, a `run` line ending a sentence, a `caesura` line with no pause;
- rhyme: lines under one tag whose last words end differently as spelled. This misses rhymes spelled differently
  (only sky, high and a few like them are joined) and counts an eye rhyme (gone, stone) as a rhyme. Also a rhyme
  word used twice;
- refrain and `ends` lines are exempt from the repeated-word check.
````

- [ ] **Step 3: Write the templates**

Create `plugins/wrist/skills/wrist/assets/templates/poem/PREMISE.md`:

````markdown
---
profile: poem
title: <Working title, or the printed title if the poem is titled>
slug: <lower-case-words-joined-by-hyphens>
author: <Author name>
language: en
titled: <yes or no; no by default>
---

# Premise

<One or two sentences: what this poem is.>

## Answers

- **subject:** <answer or *UNKNOWN*: [name] <what>. Kind: blocking. Consequence: <...>. Unlocks: <...>.>
- **form:** <a catalog form, custom, or *UNKNOWN* with your Proposed form>
- **tone:** <answer>
- **audience:** <answer>
- **length:** <the form's own, or a number of lines>
- **speaker:** <answer>
- **occasion:** <answer>
- **rhyme:** <answer>
- **images:** <answer>
- **avoid:** <answer>
- **titled:** <yes or no>
- **epigraph:** <answer>
- **dedication:** <answer>
- **keep:** <answer>
````

Create `plugins/wrist/skills/wrist/assets/templates/poem/structure.wrist.md`:

````markdown
# structure: <Title>

Notes for the skeleton of the poem (the realized file is structure.md, written in references/psg.md's grammar).

- **Form:** <a catalog form from profiles/poem/forms.md, or custom>
- **Lines:** <number of lines in the skeleton>
- **Stanzas:** <number of stanzas in the skeleton>
- **Rhyme:** <the rhyme scheme in words>
- **Meter:** <the meter in words>
- **Rules:** <what the skeleton must keep; for a refrain form, how the refrains should change meaning>
- **Required:** always
- **Depends on:** none
- **Referred by:** [<title>](./work/<slug>.md.wrist.md)
- **Unknowns:** none
````

Create `plugins/wrist/skills/wrist/assets/templates/poem/poem.wrist.md`:

````markdown
# poem: <Title>

Notes for the poem itself.

- **Subject:** <what the poem is about, starting from a concrete thing>
- **Speaker:** <who speaks, and to whom>
- **Tone:** <the tone, and where it turns>
- **Turn:** <where the poem changes direction>
- **Ending:** <how it lands; not an explanation>
- **Must include:** <images, words or sounds that must appear>
- **Must avoid:** <what must not appear>
- **Must keep:** <the detail an editor would cut and you keep, unexplained>
- **Rules:** <voice, forbidden moves, quality rules copied from quality.md>
- **Required:** always
- **Depends on:** [structure](../structure.md.wrist.md) (realizes)
- **Referred by:** none
- **Unknowns:** none
````

Create `plugins/wrist/skills/wrist/assets/templates/poem/skeleton.md`:

````text
(* structure.md: copy a form from profiles/poem/forms/ and edit it, or write your own.
   See references/psg.md for the grammar. *)
poem {
  named "villanelle";
  refrain R1 at 1, 6, 12, 18;
  refrain R2 at 3, 9, 15, 19;
  stanza (tercet, 5, A B A) {
    line (iamb 5, stop, A) { image["<what this line holds>"] }
    line (iamb 5, stop, B) { image["<what this line holds>"] }
    line (iamb 5, stop, A) { image["<what this line holds>"] }
  }
  stanza (quatrain, 1, A B A A) {
    line (iamb 5, stop, A) { }
    line (iamb 5, stop, B) { }
    line (iamb 5, stop, A) { }
    line (iamb 5, stop, A) { }
  }
}
````

- [ ] **Step 4: Edit the skill, the grammar and publishing references, the README and the manifest**

Save this as `/tmp/docs_edit.py` and run `python3 /tmp/docs_edit.py .` from the repository root; each replacement asserts its anchor exists once (read an assertion failure as a drifted anchor and fix the anchor, not the intent).

````python
import sys
ROOT = sys.argv[1]
def edit(rel, pairs):
    p = f"{ROOT}/{rel}"
    s = open(p, encoding="utf-8").read()
    for old, new in pairs:
        assert s.count(old) == 1, (rel, old[:70])
        s = s.replace(old, new)
    open(p, "w", encoding="utf-8").write(s)

S = "plugins/wrist/skills/wrist/SKILL.md"
edit(S, [
 ("description: Write a prose work (short story, with novel, screenplay and poem to follow) in four phases",
  "description: Write a prose or verse work (short story, novel, screenplay or poem) in four phases"),
 ("Three profiles exist: `shortstory`, `novel` and `screenplay`. If the user wants a poem, say it is not built yet. Each profile has its own folder under `profiles/` (questions, structures, quality lists) and its own templates: `assets/templates/` for the short story, `assets/templates/novel/` for the novel and `assets/templates/screenplay/` for the screenplay. A screenplay's acts are written in Fountain; read `references/fountain.md` before writing one.",
  "Four profiles exist: `shortstory`, `novel`, `screenplay` and `poem`. Each profile has its own folder under `profiles/` (questions, structures or forms, quality lists) and its own templates: `assets/templates/` for the short story, `assets/templates/novel/` for the novel, `assets/templates/screenplay/` for the screenplay and `assets/templates/poem/` for the poem. A screenplay's acts are written in Fountain; read `references/fountain.md` before writing one. A poem is planned as a skeleton in the grammar of `references/psg.md` (the standard forms are ready-made skeletons in `profiles/poem/forms/`) and written as plain verse; read `references/verse.md` before writing one."),
 ("1. Ask which profile (`shortstory`, `novel` or `screenplay`) and read",
  "1. Ask which profile (`shortstory`, `novel`, `screenplay` or `poem`) and read"),
 ("A page is about a minute, so ask for the runtime and keep the page targets in the outline honest.",
  "A page is about a minute, so ask for the runtime and keep the page targets in the outline honest. For a poem the front matter holds `titled:` (`yes` or `no`; no unless the author wants a title) and the `title:` is always needed: the printed title when `titled: yes`, otherwise a working title for the file names. Never invent a title for an untitled poem."),
 ("Create the empty files first so links have targets.",
  "For a poem write two stand-ins, `structure` and `poem`, from `assets/templates/poem/`; the structure stand-in states `Form:` (a catalog form or `custom`), `Lines:` and `Stanzas:`. Create the empty files first so links have targets."),
 ("`stamp` refuses an act whose `Established:` is empty.\n3. Craft rules",
  "`stamp` refuses an act whose `Established:` is empty. For a poem, realize `structure.md` first: the skeleton, in the grammar of `references/psg.md`. Copy the catalog form from `profiles/poem/forms/` when the form is one of them and keep its `named` line; write your own skeleton for `custom`. Run `wrist_check.py verse wrist` until the only error left is that the poem does not exist, then stamp it. Then write `work/<slug>.md` as plain verse (`references/verse.md`): one line of verse per line, a blank line between stanzas, a `# Title` first line only when `titled: yes`, never a line wrapped by hand. Run `verse` again: errors must be fixed, estimates are advisory. If a line fails, revise the line, not the skeleton.\n3. Craft rules"),
 ("Fix what fails, re-stamp, and only then set `review_done: yes` in `PREMISE.md`.",
  "For a poem the review includes deleting the last line to see whether the poem is better, rebreaking half the lines that end at a natural pause, and replacing every word on the ban list with a specific object. Fix what fails, re-stamp, and only then set `review_done: yes` in `PREMISE.md`."),
 ("Record everything in `PREMISE.md`, then set `questions_publishing: done`.",
  "For a poem also ask for the optional `dedication:` and `epigraph:` (one line each) and the paper (`trim:`; A5 by default). Record everything in `PREMISE.md`, then set `questions_publishing: done`."),
 ("python3 \"${CLAUDE_SKILL_DIR}/scripts/wrist_check.py\" lint WRIST_DIR [--root .]\n",
  "python3 \"${CLAUDE_SKILL_DIR}/scripts/wrist_check.py\" lint WRIST_DIR [--root .]\npython3 \"${CLAUDE_SKILL_DIR}/scripts/wrist_check.py\" verse WRIST_DIR [--root .] [--json]\n"),
])
edit("README.md", [("`shortstory`, `novel` and `screenplay` exist; the\npoem profile is planned.",
                    "`shortstory`, `novel`, `screenplay` and `poem` exist.")])
edit("plugins/wrist/.claude-plugin/plugin.json", [
 ("Profiles: short story, novel and screenplay", "Profiles: short story, novel, screenplay and poem"),
 ('"epub", "publishing"]', '"epub", "publishing", "poetry"]')])
edit("plugins/wrist/skills/wrist/references/grammar.md", [
 ("`story`, `book` or `screenplay`.", "`story`, `book`, `screenplay` or `poem`."),
 ("- **`lint_format`**:", "- **`form`**: for a poem profile, an object with the paths `structure` and `poem`, both listed in `files`. The structure file is a skeleton in the grammar of `psg.md`, the poem is plain verse (`verse.md`), and the `verse` command and `gate publishing` check the poem against the skeleton. A profile with `style: poem` is published in poem layout.\n- **`lint_format`**:"),
])
edit("plugins/wrist/skills/wrist/references/publishing.md", [
 ("## When the build fails",
  "## A poem\n\nA poem is read with the verse reader and set as verse: A5 (any Typst paper with `trim:`), 11 pt Libertinus Serif with generous leading, flush left, never justified or reflowed, each leading space of a line half an em of indent, a line too long for the page wrapped with a hanging indent, a stanza that fits on a page kept whole. A `dedication:` (italic, right) comes first, then the title when `titled: yes`, the author as an italic byline and an optional `epigraph:`. An untitled poem prints the byline and the verse with no title. The page number shows from the second page. The EPUB has the same elements; its contents list the working title, and an untitled poem's heading is hidden on the page. No title page, copyright page or contents page is built.\n\n## When the build fails"),
])
````

- [ ] **Step 5: Run the tests**

Run: `python3 -m unittest discover -s plugins/wrist/tests -p "test_docs.py" -q 2>&1 | tail -4`
Expected: `Ran 24 tests` and `OK`.

Run: `python3 -m unittest discover -s plugins/wrist/tests -q 2>&1 | tail -3`
Expected: `Ran 528 tests`, `OK`.

- [ ] **Step 6: Commit**

```bash
git add plugins/wrist/skills/wrist/SKILL.md plugins/wrist/skills/wrist/references plugins/wrist/skills/wrist/assets/templates/poem README.md plugins/wrist/.claude-plugin/plugin.json plugins/wrist/tests/test_docs.py
git commit -m "docs(wrist): teach the skill and references the poem profile" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01BbGUbm5dYKZovMogE1FAjn"
```

---


### Task 11: Trial: a fresh session writes a short poem

This task is performed by the executor, not by a test. Each earlier trial found defects the test suites could not, so it is required for the cycle to be called done.

**Files:**
- Create: `notes/wrist-poem-trial.md` (untracked notes)
- Modify: whatever the trial exposes, with a failing test first for each code defect

- [ ] **Step 1: Set up the harness**

```bash
S=/tmp/claude-1000/-home-sean-Data-Projects-claude-plugins/b823c3ae-57a6-454b-b3b3-63ef3fa1a7f8/scratchpad
rm -rf $S/ptrial && mkdir -p $S/ptrial && cd $S/ptrial && git init -q .
sed 's#/strial#/ptrial#; s#sturn-#pturn-#g' $S/sturn.sh > $S/pturn.sh && chmod +x $S/pturn.sh
grep -n "ptrial\|pturn" $S/pturn.sh | head -4
```

- [ ] **Step 2: Run the conversation**

Four to six resumed turns, playing the author, with a premise unlike the example: a short poem about a bakery at four in the morning, **form left open** ("choose for me"), untitled (`titled: no`), dedication wanted, tone dry and warm, a `keep` detail given (the baker counts the loaves aloud in another language), a deliberate gap (skip occasion and epigraph). Turn 1: "I'd like to write a poem." Then answer its questions, accept its proposals, and ask it to continue through generation, realization and publishing. Record each turn's cost and result.

- [ ] **Step 3: Inspect the output yourself**

Read every stand-in, `structure.md` and the poem. Run `check`, `status`, `verse`, `lint` and the three gates with the plugin's scripts. Render the PDF pages (the scratch virtualenv) and look at the layout (untitled: byline and verse, no title); open the EPUB structure. Compare the work with the stand-ins as the author: did it pick a form and record it as an `*UNKNOWN*:` with `Proposed:`; copy a catalog skeleton and keep its `named` line; write the skeleton before the poem; revise the line rather than the skeleton when `verse` complained; keep the refrains' meaning moving; use banned words; add facts the stand-ins do not hold; put `Must keep:` in the poem unexplained?

- [ ] **Step 4: Fix and record**

For each defect: a failing test first for a code defect, the smallest fix, the suite green, a commit. Guidance defects go into `SKILL.md` with a test pinning the phrase. Write the findings in `notes/wrist-poem-trial.md`, each marked `[observed]` or `[not verified]`, and say what was fixed and what was left. Do not report anything as a mistake before you have checked it against the stand-ins and the premise.

- [ ] **Step 5: Commit**

```bash
git add -A plugins/wrist
git commit -m "fix(wrist): close the defects the poem trial exposed" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01BbGUbm5dYKZovMogE1FAjn"
```

(Skip if the trial exposed nothing to fix, and say so.)

---

### Task 12: Whole-plugin verification

- [ ] **Step 1: Full suites**

Run: `python3 -m unittest discover -s plugins/wrist/tests -q 2>&1 | tail -4; python3 -m unittest discover -s plugins/skel/tests -q 2>&1 | tail -3`
Expected: wrist `OK` (528 tests, or more if the trial added some) with no skips (pandoc and typst are installed); skel `OK` (223 tests), unchanged.

- [ ] **Step 2: All four examples as a user**

```bash
cd /home/sean/Data/Projects/claude-plugins/plugins/wrist/skills/wrist/assets/examples
S=../../../scripts/wrist_check.py
for e in the-lamp salt-road the-third-bell counting; do (cd $e && echo "-- $e" && python3 $S check wrist | tail -1 && python3 $S status wrist | head -1 && python3 $S lint wrist | grep hits && for p in generation realization publishing; do python3 $S gate wrist $p; done; ls); done
cd counting && python3 ../../../scripts/wrist_check.py verse wrist --root . | tail -1
```

Expected: all `0 errors, 0 warnings`, every file realized, 0 lint hits, all twelve gates open, no `output/` folder in any example, and `0 errors, 0 estimates` from `verse`.

- [ ] **Step 3: Leftover scan**

Run: `grep -rniE "skel|TODO|TBD|FIXME" plugins/wrist -I | grep -vi 'skelet' | grep -v 'tests/'`
Expected: only the informal-marker regex, the `todo` variable names in `wrist_check.py` and the grammar's description of informal markers. (The word skeleton is the poem profile's own term and is excluded by the second filter.)

- [ ] **Step 4: Bring the spec in line**

Edit `docs/superpowers/specs/2026-10-04-wrist-poem-design.md` where the build departed from it (including anything the trial changed), adding each departure as a numbered line under "Open decisions", and commit with the final fixes.

```bash
git add -A docs plugins/wrist
git commit -m "docs(wrist): bring the poem spec in line with the build" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01BbGUbm5dYKZovMogE1FAjn"
```

---

## Self-review

**1. Spec coverage**

| Spec section | Task |
|---|---|
| Decisions: PSGv2 as the language of `structure.md`, fixed; exact errors and advisory estimates; plain verse with a Lua reader; the agent writes `structure.md`; the prompt rules adopted; title optional | 1 to 9, 7 (quality, lint, `titled`) |
| The ten PSGv2 fixes; roles optional (`strict roles;`); the grammar; rules R0 to R12 | 1, 2 (and `references/psg.md` in 10) |
| The catalog and its tests; terza rima, ghazal and rondeau out of scope | 6 |
| File shape, stand-in functions, premise key `titled`, questions, `forms.md` | 7 |
| `verse` command: skeleton, stand-in agreement, named form, poem exact checks, estimates, exit codes, gate | 3 to 6, 9 |
| The verse reader (Lua and Python) and shared cases | 3 |
| Publishing: layout, heading block, EPUB, pipeline | 8, 9 |
| Quality data: `quality.md`, checklist, `lint.json` | 7 |
| Skill, references, templates, README | 10 |
| Example and tests; the trial | 9, 1 to 9, 11 |
| Out of scope (collections, terza rima, ghazal, rondeau, concrete poems, prose poems, scansion, non-English, audio, TEI) | not built |
| Open decisions 1 to 9 | built as written; the paper and the layout verified by looking (Tasks 8, 9) |

Departures from the spec, all made while prototyping and already written into it: `breaks flexible;` is a declaration (the sonnets and blank verse need it); R9 estimates only the syllable count, not stress positions; R12 compares with the list item, not with "the same word"; a printed title must equal the front matter title; missing files and broken skeletons end the run in a stated order; the structure stand-in's `Form`, `Lines` and `Stanzas` are `required_when_realized`; in the EPUB the dedication follows the title heading because a heading must come first.

**2. Placeholder scan:** none; every step shows its code. The `<...>` markers in templates are intended slots.

**3. Type consistency:** the module is built in layers and each task lists what it consumes and produces. `Problem(severity, line, message)` is the one record used by the parser rules, the exact checks, the estimates and the catalog comparison; `verse_problems` turns them into `(severity, file, line, message)`. `Verse.stanzas` holds `(line number, text)` pairs everywhere. `XLine.tag` is the renamed tag everywhere (refrain and rhyme checks), `XLine.line.tag` the declared one. Premise key `titled` and question id `titled` agree between `profile.json`, `questions.md`, the example's `PREMISE.md` and the tests; the profile's `form` paths match the file entries.

**4. Review Focus coverage:** item 1 is `Refrains` in Task 4; 2 is `test_a_skeleton_with_rule_errors_leaves_the_poem_unchecked` and its siblings in Task 9; 3 is `PoemPlan`, `LuaReader` and `RealBuild`; 4 is `RealBuild` and the contents check in Task 9 step 6; 5 is `Titles` (Task 4) and `test_the_title_line_must_match_titled` (Task 9); 6 is the missing-file tests in Task 9; 7 is `test_a_repeating_form_resolves_its_count_from_the_lines` in Task 6.

**Known risks the executor should watch:**
- Tasks 7 to 10 apply patches with `git apply`; if one fails because a file drifted, read the hunk and apply the same change by hand, then say so in the ledger.
- The layout (indents, hanging wrap, byline, page numbers) is verified only by looking at rendered pages; Task 8 step 6 and Task 9 step 6 are not optional.
- The estimates will sometimes be wrong (an eye rhyme counted as a rhyme, "being" as one syllable). That is documented; do not make them exact.
- The trial costs money and time; keep the poem short.

