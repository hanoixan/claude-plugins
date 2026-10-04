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
