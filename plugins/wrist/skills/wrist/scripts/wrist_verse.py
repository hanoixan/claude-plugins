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
