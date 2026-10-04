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
