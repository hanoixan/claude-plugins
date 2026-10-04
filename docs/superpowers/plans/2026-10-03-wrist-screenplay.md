# wrist screenplay profile (cycle 3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the `screenplay` profile to wrist: acts written in Fountain, read by a pandoc Lua reader, and published as a screenplay-layout PDF and a reading EPUB.

**Architecture:** The planning side reuses the novel's engine (an `acts` family fixed by `PREMISE.md`, `Established:`, `sequence`). New pieces: a `publish.style` profile setting with a style registry in `wrist_publish.py`; a `lint_format` setting with a Fountain line classifier in `wrist_lint.py`; a Fountain reader, a Typst filter, a page template and a stylesheet under `publish/screenplay/`. The reader (Lua) and the classifier (Python) implement the same rules and are tested against one shared case file. Every layout and reader piece in this plan was prototyped with the real tools before the plan was written.

**Tech Stack:** Python 3.10 standard library (scripts and `unittest`); pandoc 3.12 (custom Lua reader, Lua filters) and typst 0.15 for the real builds (installed on this machine; real-build tests skip when absent).

**Spec:** `docs/superpowers/specs/2026-10-03-wrist-screenplay-design.md` (builds on the foundation and novel specs)

## Global Constraints

- Scripts and tests use only the Python standard library; profiles are JSON.
- The checker stays generic: no screenplay vocabulary in `wrist_check.py` or `wrist_profile.py`. Fountain knowledge lives in `wrist_lint.py`, `wrist_publish.py` and `publish/screenplay/`.
- The short story and novel profiles, examples and all their tests keep passing unchanged. A profile with no `publish` key keeps today's inferred style (`book` if it has a `sequence` function, else `story`).
- Stand-ins hold notes, never final text. `plugins/skel/` is not modified.
- The Lua reader and the Python classifier follow the rules in `tests/fountain_cases.json`; changing a rule means changing that file first.
- Fonts: the screenplay font list is Courier Prime, Courier New, DejaVu Sans Mono; the last is bundled with typst.
- The test suite has no PDF reader. Layout, page numbers and indents are verified by rendering pages and looking at them (a scratch virtualenv with `pymupdf`), and the Typst the filter emits is asserted in tests.

## Review Focus

Inputs the spec implies that no obvious test would reach. Each has a test in the task that owns the code.

1. A Fountain line that looks like another element must not become the wrong one: a heading with no blank line after it, an upper-case line inside action, a character cue with no dialogue, `INTERIOR design`, `..` and `!` forced forms. Tasks 1 and 2 (shared cases).
2. Changing `acts:` after generation fails `check` ("required stand-in missing", "outside the screenplay shape"). Task 5.
3. Title page lines with `&`, `#`, quotes and accents reach the PDF and EPUB intact. Task 3.
4. Page numbering: the title page and the first script page carry no number, later pages show "2." onward; an act heading says "ACT TWO", not "TWO", and starts a new page. Task 3 (Typst assertions plus a rendered-page check).
5. Lint scopes: `we see` in dialogue is not flagged by an action-only pattern, `as you know` in action is not flagged by a dialogue-only one, and hit line numbers stay right after a multi-line note. Task 1.
6. The EPUB contents list no stray entry named after the script. Task 3.

---

## File structure

```text
plugins/wrist/
  skills/wrist/
    scripts/wrist_profile.py     edited: publish, lint_format, scopes by format
    scripts/wrist_lint.py        edited: Fountain classifier, Fountain-aware lint_text
    scripts/wrist_publish.py     edited: style registry, screenplay plan, act markers
    scripts/wrist_check.py       edited: cmd_lint passes the format; cmd_publish by style
    profiles/screenplay/         profile.json, questions.md, structures.md, quality.md, lint.json
    publish/screenplay/          fountain.lua, screenplay.lua, screenplay.typ, screenplay.css
    assets/templates/screenplay/ six templates
    assets/examples/the-third-bell/   complete tiny screenplay
    references/fountain.md (new), grammar.md, publishing.md, SKILL.md   edited
  tests/fountain_cases.json (new), test_screenplay_engine.py, test_fountain.py,
        test_screenplay_publish.py, test_screenplay.py (new); support.py, test_docs.py (edited)
```

---

### Task 1: Profile settings, the Fountain classifier and Fountain-aware lint

**Files:**
- Modify: `plugins/wrist/skills/wrist/scripts/wrist_profile.py`, `wrist_lint.py`, `wrist_check.py` (`cmd_lint` only)
- Create: `plugins/wrist/tests/fountain_cases.json`, `plugins/wrist/tests/test_screenplay_engine.py`, `plugins/wrist/tests/test_fountain.py`

**Interfaces:**
- Produces in `wrist_profile`: `Profile.publish_style: str | None` (from `publish: {"style": name}`), `Profile.lint_format: "prose" | "fountain"` (default `"prose"`), `LINT_FORMATS = ("prose", "fountain")`, `SCOPES: dict[format, tuple]` (`prose`: `narration`, `anywhere`; `fountain`: `action`, `dialogue`, `anywhere`). `lint_items()` validates `scope` against the profile's format; the error reads `scope must be one of <list>`. `OPTIONAL_KEYS` gains `publish` and `lint_format`.
- Produces in `wrist_lint`: `strip_comments(text)` (removes `/* */` and `[[ ]]`, as the reader does), `mask_comments(text)` (blanks them with spaces, keeping every newline), `classify_fountain(text) -> list[(line_number, kind, text)]` where `text` is the comment-masked line and `kind` is one of `heading action character parenthetical dialogue transition centered pagebreak marker dropped blank`, `elements(text) -> list[str]` (the reader's element kinds in order, with `heading` as `scene-heading` and `marker` as `act-marker`, consecutive dialogue lines or action lines as one element, blank and dropped lines producing none), and `lint_text(text, items, lint_format="prose")` (unchanged for `prose`; for `fountain` a hit counts only when its line's kind fits the item's scope: `action` = kind `action`; `dialogue` = `dialogue` or `parenthetical`; `anywhere` = any kind except `blank`, `dropped`, `pagebreak`, `marker`; patterns are matched against the comment-masked line).
- `cmd_lint` passes `profile.lint_format`.

- [ ] **Step 1: Write the shared cases**

Create `plugins/wrist/tests/fountain_cases.json`:

```json
[
 {"name": "heading then action", "text": "INT. KITCHEN - DAY\n\nShe waits.\n", "kinds": ["scene-heading", "action"]},
 {"name": "a heading with no blank before it is action", "text": "She waits.\nINT. KITCHEN - DAY\n\nMore.\n", "kinds": ["action", "action"]},
 {"name": "an upper-case heading with no blank after reads as a character cue", "text": "INT. KITCHEN - DAY\nShe waits.\n", "kinds": ["character", "dialogue"]},
 {"name": "lower case int heading", "text": "int. kitchen - day\n\nShe waits.\n", "kinds": ["scene-heading", "action"]},
 {"name": "I/E and INT./EXT. forms", "text": "I/E CAR - MOVING\n\nGo.\n\nINT./EXT. HOUSE - DAY\n\nGo.\n", "kinds": ["scene-heading", "action", "scene-heading", "action"]},
 {"name": "INTERIOR is not a heading", "text": "INTERIOR design is hard.\n\nOk.\n", "kinds": ["action", "action"]},
 {"name": "forced heading", "text": ".THE BEACH\n\nWaves.\n", "kinds": ["scene-heading", "action"]},
 {"name": "double dot is not a forced heading", "text": "..and so on\n\nOk.\n", "kinds": ["action", "action"]},
 {"name": "dialogue block", "text": "MARIT\n(quietly)\nTwenty-three.\nI counted twice.\n\nHALLORAN (O.S.)\nLog says twenty-four.\n", "kinds": ["character", "parenthetical", "dialogue", "character", "dialogue"]},
 {"name": "a character cue needs a blank line before it", "text": "She says:\nMARIT\nHello.\n", "kinds": ["action"]},
 {"name": "a character cue needs dialogue after it", "text": "Fog.\n\nMARIT\n\nSilence.\n", "kinds": ["action", "action", "action"]},
 {"name": "forced character", "text": "@McCLOUD\nHi.\n", "kinds": ["character", "dialogue"]},
 {"name": "character with numbers and an extension", "text": "AGENT 47 (CONT'D)\nStill here.\n", "kinds": ["character", "dialogue"]},
 {"name": "transition", "text": "Fog.\n\nCUT TO:\n\nEXT. GATE - DUSK\n\nSea.\n", "kinds": ["action", "transition", "scene-heading", "action"]},
 {"name": "forced transition", "text": "Fog.\n\n> Burn to white.\n\nSea.\n", "kinds": ["action", "transition", "action"]},
 {"name": "centered", "text": "> THE END <\n", "kinds": ["centered"]},
 {"name": "page break", "text": "One.\n\n===\n\nTwo.\n", "kinds": ["action", "pagebreak", "action"]},
 {"name": "forced action", "text": "!MARIT\n", "kinds": ["action"]},
 {"name": "notes and boneyard are removed", "text": "/* gone */\nINT. A - DAY\n\nText [[a note]] here.\n\n[[whole\nnote]]\n\nMore.\n", "kinds": ["scene-heading", "action", "action"]},
 {"name": "sections and synopses are dropped", "text": "# Act one\n\n= the synopsis\n\nINT. A - DAY\n\nText.\n", "kinds": ["scene-heading", "action"]},
 {"name": "act marker", "text": "@@ACT ONE@@\n\nINT. A - DAY\n\nText.\n", "kinds": ["act-marker", "scene-heading", "action"]},
 {"name": "an upper-case line inside action is action", "text": "He reads.\nSTOP\nHe stops.\n", "kinds": ["action"]},
 {"name": "crlf line endings", "text": "INT. A - DAY\r\n\r\nText.\r\n", "kinds": ["scene-heading", "action"]},
 {"name": "empty text", "text": "", "kinds": []},
 {"name": "only blank lines", "text": "\n\n  \n", "kinds": []}
]
```

- [ ] **Step 2: Write the failing tests**

Create `plugins/wrist/tests/test_fountain.py`:

```python
import json
import os
import unittest

from support import HERE     # first: it puts the scripts folder on sys.path

import wrist_lint

with open(os.path.join(HERE, "fountain_cases.json"), encoding="utf-8") as fh:
    CASES = json.load(fh)


class SharedCases(unittest.TestCase):
    def test_the_python_classifier_follows_every_shared_case(self):
        for case in CASES:
            with self.subTest(case["name"]):
                self.assertEqual(wrist_lint.elements(case["text"]), case["kinds"])


class LineKinds(unittest.TestCase):
    def kinds(self, text):
        return [(n, k) for n, k, _ in wrist_lint.classify_fountain(text)]

    def test_every_line_gets_a_kind_with_its_own_number(self):
        text = "INT. A - DAY\n\nMARIT\n(softly)\nHi.\n\nCUT TO:\n"
        self.assertEqual(self.kinds(text), [(1, "heading"), (2, "blank"), (3, "character"), (4, "parenthetical"),
                                            (5, "dialogue"), (6, "blank"), (7, "transition"), (8, "blank")])

    def test_comments_are_blanked_but_every_line_keeps_its_number(self):
        text = "[[a\nb]]\n\nWe see it.\n"
        kinds = self.kinds(text)
        self.assertEqual(kinds[3], (4, "action"))
        self.assertEqual(wrist_lint.mask_comments(text).count("\n"), text.count("\n"))

    def test_masked_text_does_not_leak_into_the_line(self):
        _, kind, line = wrist_lint.classify_fountain("Text [[secret]] here.\n")[0]
        self.assertNotIn("secret", line)
        self.assertEqual(kind, "action")

    def test_strip_comments_removes_what_the_reader_removes(self):
        self.assertEqual(wrist_lint.strip_comments("a /* x */ b [[y]] c"), "a  b  c")


class FountainLint(unittest.TestCase):
    ITEMS = [
        {"id": "we-see", "pattern": r"\bwe see\b", "label": "l", "note": "n", "scope": "action"},
        {"id": "as-you-know", "pattern": r"\bas you know\b", "label": "l", "note": "n", "scope": "dialogue"},
        {"id": "anywhere", "pattern": r"\bfog\b", "label": "l", "note": "n", "scope": "anywhere"},
    ]

    def hits(self, text):
        return [(h["line"], h["id"]) for h in wrist_lint.lint_text(text, self.ITEMS, "fountain")]

    def test_review_focus_an_action_pattern_ignores_dialogue(self):
        self.assertEqual(self.hits("MARIT\nWe see it, as you know.\n"), [(2, "as-you-know")])

    def test_review_focus_a_dialogue_pattern_ignores_action(self):
        self.assertEqual(self.hits("As you know, we see it.\n"), [(1, "we-see")])

    def test_a_dialogue_pattern_reaches_parentheticals(self):
        self.assertEqual(self.hits("MARIT\n(as you know)\nHi.\n"), [(2, "as-you-know")])

    def test_an_anywhere_pattern_reaches_headings_dialogue_and_transitions(self):
        text = "EXT. FOG BANK - DAY\n\nMARIT\nThe fog.\n\nFOG TO:\n"
        self.assertEqual(self.hits(text), [(1, "anywhere"), (4, "anywhere"), (6, "anywhere")])

    def test_review_focus_hit_line_numbers_survive_a_multi_line_note(self):
        self.assertEqual(self.hits("[[a\nb]]\n\nWe see it.\n"), [(4, "we-see")])

    def test_text_inside_notes_and_boneyard_is_not_linted(self):
        self.assertEqual(self.hits("Quiet. [[we see this]]\n\n/* we see that */\n"), [])

    def test_prose_format_is_unchanged(self):
        items = [{"id": "x", "pattern": "dark", "label": "l", "note": "n", "scope": "narration"}]
        self.assertEqual(len(wrist_lint.lint_text("It was dark.", items)), 1)
        self.assertEqual(wrist_lint.lint_text('"dark," he said.', items), [])


if __name__ == "__main__":
    unittest.main()
```

Create `plugins/wrist/tests/test_screenplay_engine.py`:

```python
import json
import os
import shutil
import tempfile
import unittest

from support import TreeCase     # first: it puts the scripts folder on sys.path

import wrist_profile as wp


def base(**extra):
    data = {"name": "tiny", "files": [{"path": "a.md", "function": "a", "order": 1}],
            "functions": {"a": {"heading": "a", "prose": True}}, "relations": [], "limits": {"max_prose_words": 50}}
    data.update(extra)
    return data


class Settings(unittest.TestCase):
    def test_defaults(self):
        p = wp.parse_profile(base())
        self.assertIsNone(p.publish_style)
        self.assertEqual(p.lint_format, "prose")

    def test_a_publish_style_is_read(self):
        self.assertEqual(wp.parse_profile(base(publish={"style": "screenplay"})).publish_style, "screenplay")

    def test_publish_must_be_an_object_with_only_a_style_name(self):
        for bad in ("screenplay", {}, {"style": 3}, {"style": "Bad Name"}, {"style": "ok", "colour": 1}):
            with self.subTest(bad=bad):
                with self.assertRaises(wp.ProfileError) as cm:
                    wp.parse_profile(base(publish=bad))
                self.assertIn("'publish'", str(cm.exception))

    def test_lint_format_must_be_known(self):
        self.assertEqual(wp.parse_profile(base(lint_format="fountain")).lint_format, "fountain")
        with self.assertRaises(wp.ProfileError) as cm:
            wp.parse_profile(base(lint_format="markdown"))
        self.assertIn("'lint_format' must be one of prose, fountain", str(cm.exception))


class ScopesFollowTheFormat(unittest.TestCase):
    GOOD = {"id": "x", "pattern": "a", "label": "l", "note": "n", "scope": "anywhere", "positive": "a", "negative": "b"}

    def load(self, lint_format, scope):
        d = tempfile.mkdtemp(prefix="wrist-scope-")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        os.makedirs(os.path.join(d, "t"))
        with open(os.path.join(d, "t", "profile.json"), "w") as fh:
            json.dump(base(lint_format=lint_format), fh)
        with open(os.path.join(d, "t", "lint.json"), "w") as fh:
            json.dump({"items": [dict(self.GOOD, scope=scope)]}, fh)
        return wp.load_profile("t", d).lint_items()

    def test_fountain_scopes_are_accepted_for_a_fountain_profile(self):
        for scope in ("action", "dialogue", "anywhere"):
            self.assertEqual(len(self.load("fountain", scope)), 1)

    def test_prose_scopes_are_rejected_for_a_fountain_profile(self):
        with self.assertRaises(wp.ProfileError) as cm:
            self.load("fountain", "narration")
        self.assertIn("scope must be one of action, dialogue, anywhere", str(cm.exception))

    def test_fountain_scopes_are_rejected_for_a_prose_profile(self):
        with self.assertRaises(wp.ProfileError) as cm:
            self.load("prose", "action")
        self.assertIn("scope must be one of narration, anywhere", str(cm.exception))

    def test_the_existing_profiles_still_load(self):
        self.assertEqual(wp.load_profile("shortstory").lint_format, "prose")
        self.assertEqual(wp.load_profile("novel").lint_format, "prose")
        self.assertGreater(len(wp.load_profile("novel").lint_items()), 20)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run to verify it fails**

Run: `python3 -m unittest discover -s plugins/wrist/tests -p 'test_fountain.py' 2>&1 | tail -3; python3 -m unittest discover -s plugins/wrist/tests -p 'test_screenplay_engine.py' 2>&1 | tail -3`
Expected: FAILED/ERROR for both (`wrist_lint` has no classifier; `publish_style` and `lint_format` do not exist).

- [ ] **Step 4: Edit `wrist_profile.py`**

Apply with this script (it asserts each anchor):

```bash
cd /home/sean/Data/Projects/claude-plugins/plugins/wrist/skills/wrist/scripts && python3 - <<'PYEOF'
s = open("wrist_profile.py", encoding="utf-8").read()
def rep(old, new):
    global s
    assert old in s, old[:70]
    s = s.replace(old, new, 1)
rep('OPTIONAL_KEYS = {"title_page", "premise_keys"}', 'OPTIONAL_KEYS = {"title_page", "premise_keys", "publish", "lint_format"}')
rep('SCOPES = ("narration", "anywhere")\n',
    'LINT_FORMATS = ("prose", "fountain")\nSCOPES = {"prose": ("narration", "anywhere"), "fountain": ("action", "dialogue", "anywhere")}\n')
rep('''    if not (isinstance(data["name"], str) and NAME_RE.match(data["name"])):''',
'''    publish = data.get("publish")
    if publish is not None and not (isinstance(publish, dict) and set(publish) == {"style"}
                                    and isinstance(publish["style"], str) and NAME_RE.match(publish["style"])):
        raise ProfileError("'publish' must be an object with only a 'style' name")
    if data.get("lint_format", "prose") not in LINT_FORMATS:
        raise ProfileError(f"'lint_format' must be one of {', '.join(LINT_FORMATS)}")
    if not (isinstance(data["name"], str) and NAME_RE.match(data["name"])):''')
rep('''        self.premise_keys = data.get("premise_keys", {})
''', '''        self.premise_keys = data.get("premise_keys", {})
        self.publish_style = (data.get("publish") or {}).get("style")
        self.lint_format = data.get("lint_format", "prose")
''')
rep('''            if item["scope"] not in SCOPES:
                raise ProfileError(f"lint item '{item['id']}': scope must be one of {', '.join(SCOPES)}")''',
'''            scopes = SCOPES[self.lint_format]
            if item["scope"] not in scopes:
                raise ProfileError(f"lint item '{item['id']}': scope must be one of {', '.join(scopes)}")''')
open("wrist_profile.py", "w", encoding="utf-8").write(s)
PYEOF
python3 -m py_compile wrist_profile.py && echo compiled
```

- [ ] **Step 5: Add the classifier and the Fountain-aware lint to `wrist_lint.py`**

Replace `plugins/wrist/skills/wrist/scripts/wrist_lint.py` with:

```python
#!/usr/bin/env python3
"""wrist_lint.py: scan text for a profile's searchable clichés. Pure functions; no file access.

Two formats: `prose` (a hit is skipped inside quoted dialogue when its scope is `narration`) and `fountain`
(screenplay text: a hit counts only on lines of the kind its scope names). The Fountain rules here must stay
the same as publish/screenplay/fountain.lua; tests/fountain_cases.json is checked against both.
"""
import re

SCENE_STARTS = ("INT./EXT", "INT/EXT", "INT", "EXT", "EST", "I/E")
NOT_LINTED = ("blank", "dropped", "pagebreak", "marker")


def in_dialogue(line, pos):
    """True when position `pos` of the line lies inside a double-quoted span that opened on this line."""
    inside = False
    for ch in line[:pos]:
        if ch == '"':
            inside = not inside
        elif ch == "“":
            inside = True
        elif ch == "”":
            inside = False
    return inside


def strip_comments(text):
    """Remove boneyard /* */ and notes [[ ]], exactly as the reader does."""
    text = text.replace("\r\n", "\n")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"\[\[.*?\]\]", "", text, flags=re.S)


def mask_comments(text):
    """Blank boneyard and notes with spaces but keep every newline, so line numbers do not move."""
    def blank(m):
        return re.sub(r"[^\n]", " ", m.group(0))
    text = text.replace("\r\n", "\n")
    text = re.sub(r"/\*.*?\*/", blank, text, flags=re.S)
    return re.sub(r"\[\[.*?\]\]", blank, text, flags=re.S)


def _blank(line):
    return line is None or not line.strip()


def _upper_name(line):
    core = re.sub(r"\s*\([^()]*\)\s*$", "", line)
    return bool(re.search(r"[^\W\d_]", core)) and core == core.upper() and bool(core.strip())


def _natural_heading(line):
    up = line.upper()
    return any(up.startswith(s) and len(up) > len(s) and up[len(s)] in ". " for s in SCENE_STARTS)


def _classify(lines):
    out, i, n = [], 0, len(lines)

    def prev_blank(k):
        return k == 0 or _blank(lines[k - 1])

    def next_blank(k):
        return k + 1 >= n or _blank(lines[k + 1])

    while i < n:
        line = lines[i]
        if _blank(line):
            out.append((i + 1, "blank", line)); i += 1
        elif re.match(r"^===+\s*$", line):
            out.append((i + 1, "pagebreak", line)); i += 1
        elif re.match(r"^@@ACT .*?@@\s*$", line):
            out.append((i + 1, "marker", line)); i += 1
        elif line.startswith("#") or (line.startswith("=") and not re.match(r"^===", line)):
            out.append((i + 1, "dropped", line)); i += 1
        elif re.match(r"^\.[^.]", line) or (_natural_heading(line) and prev_blank(i) and next_blank(i)):
            out.append((i + 1, "heading", line)); i += 1
        elif re.match(r"^>\s*.*?\s*<\s*$", line):
            out.append((i + 1, "centered", line)); i += 1
        elif line.startswith(">") or (_upper_name(line) and re.search(r"TO:\s*$", line) and prev_blank(i) and next_blank(i)):
            out.append((i + 1, "transition", line)); i += 1
        elif line.startswith("!"):
            out.append((i + 1, "action", line)); i += 1
        elif prev_blank(i) and not next_blank(i) and (line.startswith("@") or (_upper_name(line) and not re.search(r"TO:\s*$", line))):
            out.append((i + 1, "character", line)); i += 1
            while i < n and not _blank(lines[i]):
                kind = "parenthetical" if re.match(r"^\s*\(.*\)\s*$", lines[i]) else "dialogue"
                out.append((i + 1, kind, lines[i])); i += 1
        else:
            while i < n and not _blank(lines[i]):
                out.append((i + 1, "action", lines[i])); i += 1
    return out


def classify_fountain(text):
    """[(line number, kind, comment-masked line)] for every line of a Fountain text."""
    return _classify(mask_comments(text).split("\n"))


def elements(text):
    """The element kinds the Fountain reader produces, in order. Consecutive dialogue lines, and consecutive
    action lines, are one element; blank and dropped lines produce none."""
    kinds, prev = [], None
    for _, kind, _ in _classify(strip_comments(text).split("\n")):
        if kind in ("blank", "dropped"):
            prev = None
            continue
        kind = {"heading": "scene-heading", "marker": "act-marker"}.get(kind, kind)
        if kind in ("dialogue", "action") and prev == kind:
            continue
        kinds.append(kind)
        prev = kind
    return kinds


def _fits(scope, kind):
    if kind in NOT_LINTED:
        return False
    if scope == "action":
        return kind == "action"
    if scope == "dialogue":
        return kind in ("dialogue", "parenthetical")
    return True


def lint_text(text, items, lint_format="prose"):
    """Hits as dicts, sorted by line then id."""
    compiled = [(item, re.compile(item["pattern"], re.IGNORECASE)) for item in items]
    hits = []
    if lint_format == "fountain":
        numbered = [(n, line) for n, kind, line in classify_fountain(text) if kind not in NOT_LINTED]
        kinds = {n: kind for n, kind, _ in classify_fountain(text)}
    else:
        numbered = list(enumerate(text.split("\n"), 1))
        kinds = {}
    for n, line in numbered:
        for item, rx in compiled:
            if lint_format == "fountain" and not _fits(item["scope"], kinds[n]):
                continue
            for m in rx.finditer(line):
                if lint_format != "fountain" and item["scope"] == "narration" and in_dialogue(line, m.start()):
                    continue
                hits.append({"line": n, "id": item["id"], "label": item["label"],
                             "text": m.group(0), "note": item["note"]})
    return sorted(hits, key=lambda h: (h["line"], h["id"]))
```

In `wrist_check.py`, change the `cmd_lint` call `found = wrist_lint.lint_text(fh.read(), items)` to `found = wrist_lint.lint_text(fh.read(), items, profile.lint_format)`.

- [ ] **Step 6: Run the whole suite**

Run: `python3 -m unittest discover -s plugins/wrist/tests -q 2>&1 | tail -6`
Expected: `OK`. The earlier prose lint tests must still pass untouched.

- [ ] **Step 7: Commit**

```bash
git add plugins/wrist
git commit -m "feat(wrist): add publish style and lint format to profiles, and a Fountain classifier for lint" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 2: The Fountain reader

**Files:**
- Create: `plugins/wrist/skills/wrist/publish/screenplay/fountain.lua`
- Modify: `plugins/wrist/tests/test_fountain.py` (append `LuaReader`)

**Interfaces:**
- Consumes: `tests/fountain_cases.json` and `wrist_lint.elements` from Task 1.
- Produces: a pandoc custom reader, used as `pandoc --from <path>/fountain.lua`. Each element becomes a `Div` whose first class is the element kind (`scene-heading`, `action`, `character`, `dialogue`, `parenthetical`, `transition`, `centered`, `act-marker`); a page break is an empty `Div` with class `pagebreak`. Inline text is read as restricted markdown (emphasis kept; citations, raw HTML/TeX, math, bare URIs, fancy lists and smart punctuation off); a line that does not read as one paragraph (for example `1. The house`) is kept literally. The marker line `@@ACT ONE@@` becomes an `act-marker` Div whose text is `ACT ONE`.

- [ ] **Step 1: Write the failing tests**

Append to `plugins/wrist/tests/test_fountain.py`, before `if __name__ == "__main__":`, adding `import shutil`, `import subprocess` to the imports at the top:

```python
READER = os.path.normpath(os.path.join(HERE, "..", "skills", "wrist", "publish", "screenplay", "fountain.lua"))
HAVE_PANDOC = shutil.which("pandoc") is not None


def read(text):
    """The reader's top-level blocks as pandoc JSON."""
    proc = subprocess.run(["pandoc", "--from", READER, "-t", "json"], input=text, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)["blocks"]


def kind(block):
    return block["c"][0][1][0] if block["t"] == "Div" else block["t"]


def plain(blocks):
    """The text of blocks, flattened, for assertions about content."""
    out = []

    def walk(node):
        if isinstance(node, dict):
            if node.get("t") == "Str":
                out.append(node["c"])
            elif node.get("t") in ("Space", "SoftBreak", "LineBreak"):
                out.append(" ")
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(blocks)
    return "".join(out)


@unittest.skipUnless(HAVE_PANDOC, "pandoc is not installed")
class LuaReader(unittest.TestCase):
    def test_review_focus_the_reader_follows_every_shared_case(self):
        for case in CASES:
            with self.subTest(case["name"]):
                self.assertEqual([kind(b) for b in read(case["text"])], case["kinds"])

    def test_the_reader_and_the_classifier_agree_on_every_case(self):
        for case in CASES:
            with self.subTest(case["name"]):
                self.assertEqual([kind(b) for b in read(case["text"])], wrist_lint.elements(case["text"]))

    def test_emphasis_is_kept(self):
        blocks = read("She holds a *clipboard* and a **pen**.\n")
        self.assertEqual(kind(blocks[0]), "action")
        flat = json.dumps(blocks)
        self.assertIn('"t": "Emph"', flat)
        self.assertIn('"t": "Strong"', flat)

    def test_text_content_survives(self):
        text = plain(read("INT. FERRY DECK - NIGHT\n\nMARIT\n(quietly)\nTwenty-three.\n"))
        for needle in ("INT. FERRY DECK - NIGHT", "MARIT", "(quietly)", "Twenty-three."):
            self.assertIn(needle, text)

    def test_a_forced_heading_loses_its_dot_and_a_scene_number_is_dropped(self):
        text = plain(read(".THE BEACH\n\nWaves.\n\nINT. HOUSE - DAY #12#\n\nGo.\n"))
        self.assertIn("THE BEACH", text)
        self.assertNotIn(".THE", text)
        self.assertNotIn("#12#", text)

    def test_a_forced_character_loses_its_at_sign(self):
        text = plain(read("@McCLOUD\nHi.\n"))
        self.assertIn("McCLOUD", text)
        self.assertNotIn("@", text)

    def test_a_line_that_looks_like_a_list_is_kept_literally(self):
        text = plain(read("1. The house\n"))
        self.assertIn("1. The house", text)

    def test_special_characters_pass_through(self):
        text = plain(read('MARIT\nA & B #1 — "Q" café $5 @mara <Ann>\n'))
        for needle in ("A & B #1", "café", "$5", "@mara"):
            self.assertIn(needle, text)

    def test_the_act_marker_keeps_its_whole_label(self):
        block = read("@@ACT TWO@@\n\nINT. A - DAY\n\nText.\n")[0]
        self.assertEqual(kind(block), "act-marker")
        self.assertEqual(plain([block]).strip(), "ACT TWO")

    def test_a_long_script_reads_in_one_pass(self):
        script = "\n".join(f"INT. ROOM {i} - DAY\n\nMARIT\nLine {i}.\n" for i in range(100))
        self.assertEqual(len(read(script)), 300)
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m unittest discover -s plugins/wrist/tests -p test_fountain.py 2>&1 | tail -4`
Expected: FAILED (the reader file does not exist, so pandoc cannot read it).

- [ ] **Step 3: Write the reader**

Create `plugins/wrist/skills/wrist/publish/screenplay/fountain.lua`:

```lua
-- A pandoc custom reader for Fountain 1.1, the plain-text screenplay format. It emits one Div per
-- element with the element's name as its class: scene-heading, action, character, dialogue, parenthetical,
-- transition, centered, act-marker. A page break is an empty Div with class pagebreak.
-- The rules here must stay the same as wrist_lint.py; tests/fountain_cases.json is checked against both.
local OPTS = "markdown-smart-citations-raw_html-raw_tex-tex_math_dollars-autolink_bare_uris-fancy_lists"

-- Inline text is read as restricted markdown so *emphasis* works. A line that does not read as a single
-- paragraph (it looks like a list or a heading) is kept literally.
local function inlines(text)
  local blocks = pandoc.read(text, OPTS).blocks
  if #blocks == 1 and (blocks[1].t == "Para" or blocks[1].t == "Plain") then return blocks[1].content end
  return {pandoc.Str(text)}
end

local function is_blank(l) return l == nil or l:match("^%s*$") ~= nil end

local function upper_name(line)
  local core = line:gsub("%s*%b()%s*$", "")
  return core:match("%a") ~= nil and core == core:upper() and core:match("%S") ~= nil
end

local SCENE_STARTS = {"INT%./EXT", "INT/EXT", "INT", "EXT", "EST", "I/E"}
local function natural_heading(line)
  local up = line:upper()
  for _, s in ipairs(SCENE_STARTS) do
    local a, b = up:find("^" .. s)
    if a and (up:sub(b + 1, b + 1):match("[%. ]") ~= nil) then return true end
  end
  return false
end

local function div(class, text)
  return pandoc.Div({pandoc.Para(inlines(text))}, pandoc.Attr("", {class}))
end

function Reader(input)
  local text = tostring(input):gsub("\r\n", "\n"):gsub("/%*.-%*/", ""):gsub("%[%[.-%]%]", "")
  local lines = {}
  for l in (text .. "\n"):gmatch("(.-)\n") do lines[#lines + 1] = l end
  local blocks, i, n = {}, 1, #lines
  while i <= n do
    local line = lines[i]
    local prev_blank, next_blank = (i == 1) or is_blank(lines[i - 1]), is_blank(lines[i + 1])
    if is_blank(line) then
      i = i + 1
    elseif line:match("^===+%s*$") then
      blocks[#blocks + 1] = pandoc.Div({}, pandoc.Attr("", {"pagebreak"})); i = i + 1
    elseif line:match("^@@ACT .-@@%s*$") then
      blocks[#blocks + 1] = div("act-marker", line:match("^@@(ACT .-)@@%s*$")); i = i + 1
    elseif line:match("^#") or (line:match("^=") and not line:match("^===")) then
      i = i + 1                                                   -- sections and synopses are dropped
    elseif line:match("^%.[^%.]") or (natural_heading(line) and prev_blank and next_blank) then
      local t = line:gsub("^%.", ""):gsub("%s*#[%w%.%-]+#%s*$", "")
      blocks[#blocks + 1] = div("scene-heading", t); i = i + 1
    elseif line:match("^>%s*.-%s*<%s*$") then
      blocks[#blocks + 1] = div("centered", line:match("^>%s*(.-)%s*<%s*$")); i = i + 1
    elseif line:match("^>") or (upper_name(line) and line:match("TO:%s*$") and prev_blank and next_blank) then
      blocks[#blocks + 1] = div("transition", (line:gsub("^>%s*", ""))); i = i + 1
    elseif line:match("^!") then
      blocks[#blocks + 1] = div("action", (line:gsub("^!", ""))); i = i + 1
    elseif prev_blank and not next_blank and (line:match("^@") or (upper_name(line) and not line:match("TO:%s*$"))) then
      blocks[#blocks + 1] = div("character", (line:gsub("^@", ""):gsub("%^%s*$", ""))); i = i + 1
      local buf = {}
      local function flush()
        if #buf > 0 then blocks[#blocks + 1] = div("dialogue", table.concat(buf, "\n")); buf = {} end
      end
      while i <= n and not is_blank(lines[i]) do
        if lines[i]:match("^%s*%(.*%)%s*$") then
          flush(); blocks[#blocks + 1] = div("parenthetical", (lines[i]:gsub("^%s+", ""):gsub("%s+$", "")))
        else buf[#buf + 1] = lines[i] end
        i = i + 1
      end
      flush()
    else
      local buf = {}
      while i <= n and not is_blank(lines[i]) do buf[#buf + 1] = lines[i]; i = i + 1 end
      blocks[#blocks + 1] = div("action", table.concat(buf, "\n"))
    end
  end
  return pandoc.Pandoc(blocks)
end
```

- [ ] **Step 4: Run to verify it passes**

Run: `python3 -m unittest discover -s plugins/wrist/tests -q 2>&1 | tail -5`
Expected: `OK` (the `LuaReader` tests run because pandoc is installed). If a shared case disagrees between the two implementations, decide which is right by Fountain's rules, fix the wrong one and the case file together, and say so in the ledger.

- [ ] **Step 5: Commit**

```bash
git add -A plugins/wrist
git commit -m "feat(wrist): add the Fountain reader for pandoc" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 3: The screenplay publishing style

**Files:**
- Create: `plugins/wrist/skills/wrist/publish/screenplay/screenplay.lua`, `screenplay.typ`, `screenplay.css`
- Modify: `plugins/wrist/skills/wrist/scripts/wrist_publish.py`, `wrist_check.py` (`cmd_publish`)
- Create: `plugins/wrist/tests/test_screenplay_publish.py`

**Interfaces:**
- Consumes: the reader (Task 2), `Profile.publish_style` (Task 1), `Profile.options`, `Profile.functions[...]["sequence"]`.
- Produces in `wrist_publish`:
  - `STYLES = ("story", "book", "screenplay")`; `style_for(profile) -> str` (the explicit `publish_style`, else `book` when the profile has a `sequence` function, else `story`; an unknown explicit style raises `PublishError` naming the known ones).
  - `NUMBER_WORDS = ("ONE", ..., "SEVEN")`; `with_act_markers(sources, act_files, out_dir, cwd) -> (inputs, markers)` writes `<out_dir>/.wrist-act-<n>.md` containing `@@ACT <WORD>@@` and inserts each before its act file; `remove_markers(markers, cwd)`.
  - `SCREENPLAY_KEYS = ("based_on", "draft", "contact")`; `plan_screenplay(inputs, meta, out_dir, slug, publish_dir) -> [("epub", argv), ("pdf", argv)]`: `pandoc --from <publish_dir>/screenplay/fountain.lua <inputs>` with `--metadata title|author|lang` and each set screenplay key; the EPUB adds `--to epub3 --css screenplay/screenplay.css --lua-filter screenplay/screenplay.lua -o <out>/<slug>.epub`; the PDF adds `--lua-filter screenplay/screenplay.lua --template screenplay/screenplay.typ --pdf-engine=typst`, `-V papersize=<trim>` and `-V mainfont=<font>` when set, `-o <out>/<slug>.pdf`.
- `cmd_publish` resolves the style: `screenplay` reads the three keys and the premise's `act_headings`, inserts act markers when it is true, plans with `plan_screenplay` and removes the markers afterward; `story` and `book` behave exactly as before (`front_matter` is true only for `book`).

- [ ] **Step 1: Write the failing tests**

Create `plugins/wrist/tests/test_screenplay_publish.py`:

```python
import os
import shutil
import subprocess
import tempfile
import unittest
import zipfile

from support import SKILL     # first: it puts the scripts folder on sys.path

import wrist_profile
import wrist_publish

HAVE_TOOLS = shutil.which("pandoc") and shutil.which("typst")
PUBLISH_DIR = os.path.join(SKILL, "publish")
SCRIPT = ("INT. FERRY DECK - NIGHT\n\nMARIT counts faces with a clipboard.\n\nMARIT\n(quietly)\nTwenty-three.\n\n"
          "CUT TO:\n\nEXT. SEA GATE - DUSK\n\n> THE END <\n")


def fake_profile(**extra):
    data = {"name": "t", "files": [{"path": "a.md", "function": "a", "order": 1}],
            "functions": {"a": {"heading": "a", "prose": True}}, "relations": [], "limits": {"max_prose_words": 5}}
    data.update(extra)
    return wrist_profile.parse_profile(data)


class StyleResolution(unittest.TestCase):
    def test_an_explicit_style_wins(self):
        self.assertEqual(wrist_publish.style_for(fake_profile(publish={"style": "screenplay"})), "screenplay")

    def test_without_a_publish_key_the_style_is_inferred_as_before(self):
        self.assertEqual(wrist_publish.style_for(wrist_profile.load_profile("shortstory")), "story")
        self.assertEqual(wrist_publish.style_for(wrist_profile.load_profile("novel")), "book")

    def test_an_unknown_style_names_the_known_ones(self):
        with self.assertRaises(wrist_publish.PublishError) as cm:
            wrist_publish.style_for(fake_profile(publish={"style": "poster"}))
        self.assertIn("unknown publishing style 'poster'", str(cm.exception))
        self.assertIn("story, book, screenplay", str(cm.exception))


class ScreenplayPlan(unittest.TestCase):
    META = {"title": "The Third Bell", "author": "Sam Rivers", "language": "en"}

    def plan(self, **meta):
        return dict(wrist_publish.plan_screenplay(["work/act-1.md", "work/act-2.md"], dict(self.META, **meta),
                                                  "output", "the-third-bell", PUBLISH_DIR))

    def test_both_formats_read_fountain_through_the_custom_reader(self):
        reader = os.path.join(PUBLISH_DIR, "screenplay", "fountain.lua")
        for argv in self.plan().values():
            self.assertEqual(argv[:3], ["pandoc", "--from", reader])
            self.assertLess(argv.index("work/act-1.md"), argv.index("work/act-2.md"))
        self.assertTrue(os.path.isfile(reader))

    def test_the_pdf_uses_the_screenplay_template_and_filter(self):
        argv = self.plan()["pdf"]
        d = os.path.join(PUBLISH_DIR, "screenplay")
        self.assertIn("--pdf-engine=typst", argv)
        self.assertEqual(argv[argv.index("--template") + 1], os.path.join(d, "screenplay.typ"))
        self.assertEqual(argv[argv.index("--lua-filter") + 1], os.path.join(d, "screenplay.lua"))
        self.assertIn("output/the-third-bell.pdf", argv)

    def test_the_epub_uses_the_stylesheet_and_the_same_filter(self):
        argv = self.plan()["epub"]
        d = os.path.join(PUBLISH_DIR, "screenplay")
        self.assertEqual(argv[argv.index("--css") + 1], os.path.join(d, "screenplay.css"))
        self.assertEqual(argv[argv.index("--lua-filter") + 1], os.path.join(d, "screenplay.lua"))
        self.assertIn("epub3", argv)

    def test_title_page_keys_reach_both_formats_only_when_set(self):
        plan = self.plan(based_on="A short story", draft="First draft", contact="sam@example.com")
        for argv in plan.values():
            for item in ("based_on=A short story", "draft=First draft", "contact=sam@example.com"):
                self.assertIn(item, argv)
        self.assertFalse([a for a in self.plan()["pdf"] if a.startswith(("based_on=", "draft=", "contact="))])

    def test_review_focus_special_characters_stay_one_intact_argument(self):
        text = 'A & B #1 — "Q" café *x*'
        plan = self.plan(title=text, based_on=text, contact=text)
        for argv in plan.values():
            for key in ("title", "based_on", "contact"):
                self.assertIn(f"{key}={text}", argv)

    def test_trim_and_font_reach_the_pdf_only(self):
        plan = self.plan(trim="a4", font="Courier Prime")
        self.assertIn("papersize=a4", plan["pdf"])
        self.assertIn("mainfont=Courier Prime", plan["pdf"])
        self.assertNotIn("papersize=a4", plan["epub"])

    def test_no_smart_punctuation_extension_is_requested(self):
        for argv in self.plan().values():
            self.assertFalse([a for a in argv if "+smart" in a])


class ActMarkers(unittest.TestCase):
    def setUp(self):
        self.cwd = tempfile.mkdtemp(prefix="wrist-acts-")
        self.addCleanup(shutil.rmtree, self.cwd, ignore_errors=True)

    def test_a_marker_goes_before_each_act_file(self):
        sources = ["work/act-1.md", "work/act-2.md", "work/act-3.md"]
        inputs, markers = wrist_publish.with_act_markers(sources, sources, "output", self.cwd)
        self.assertEqual(inputs, ["output/.wrist-act-1.md", "work/act-1.md", "output/.wrist-act-2.md",
                                  "work/act-2.md", "output/.wrist-act-3.md", "work/act-3.md"])
        for n, word in enumerate(("ONE", "TWO", "THREE"), 1):
            with open(os.path.join(self.cwd, f"output/.wrist-act-{n}.md"), encoding="utf-8") as fh:
                self.assertEqual(fh.read(), f"@@ACT {word}@@\n")
        self.assertEqual(len(markers), 3)

    def test_remove_markers_deletes_them_and_tolerates_missing_ones(self):
        _, markers = wrist_publish.with_act_markers(["a.md"], ["a.md"], "output", self.cwd)
        wrist_publish.remove_markers(markers, self.cwd)
        self.assertFalse(os.path.exists(os.path.join(self.cwd, markers[0])))
        wrist_publish.remove_markers(markers, self.cwd)
        wrist_publish.remove_markers([], self.cwd)

    def test_seven_acts_have_names(self):
        self.assertEqual(wrist_publish.NUMBER_WORDS, ("ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN"))


@unittest.skipUnless(HAVE_TOOLS, "pandoc and typst are not installed")
class RealBuilds(unittest.TestCase):
    def setUp(self):
        self.cwd = tempfile.mkdtemp(prefix="wrist-sp-")
        self.addCleanup(shutil.rmtree, self.cwd, ignore_errors=True)
        os.makedirs(os.path.join(self.cwd, "work"))
        with open(os.path.join(self.cwd, "work", "act-1.md"), "w", encoding="utf-8") as fh:
            fh.write(SCRIPT)
        with open(os.path.join(self.cwd, "work", "act-2.md"), "w", encoding="utf-8") as fh:
            fh.write("INT. CABIN - NIGHT\n\nMore.\n")

    def build(self, inputs, **meta):
        full = dict({"title": "The Third Bell", "author": "Sam Rivers", "language": "en"}, **meta)
        plan = wrist_publish.plan_screenplay(inputs, full, "output", "tb", PUBLISH_DIR)
        wrist_publish.run_commands(plan, self.cwd)

    def typst(self, inputs):
        proc = subprocess.run(["pandoc", "--from", os.path.join(PUBLISH_DIR, "screenplay", "fountain.lua"), *inputs,
                               "-t", "typst", "--lua-filter", os.path.join(PUBLISH_DIR, "screenplay", "screenplay.lua")],
                              cwd=self.cwd, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout

    def test_both_files_are_built(self):
        self.build(["work/act-1.md", "work/act-2.md"], based_on="A short story", draft="First draft",
                   contact="sam@example.com")
        with open(os.path.join(self.cwd, "output/tb.pdf"), "rb") as fh:
            self.assertEqual(fh.read(5), b"%PDF-")
        with zipfile.ZipFile(os.path.join(self.cwd, "output/tb.epub")) as z:
            self.assertEqual(z.namelist()[0], "mimetype")

    def test_the_typst_calls_every_element_and_an_act_marker(self):
        _, markers = wrist_publish.with_act_markers(["work/act-1.md", "work/act-2.md"],
                                                    ["work/act-1.md", "work/act-2.md"], "output", self.cwd)
        typst = self.typst(["output/.wrist-act-1.md", "work/act-1.md", "output/.wrist-act-2.md", "work/act-2.md"])
        for call in ("#sp-act[", "#sp-heading[", "#sp-action[", "#sp-character[", "#sp-parenthetical[",
                     "#sp-dialogue[", "#sp-transition[", "#sp-centered["):
            self.assertIn(call, typst, call)
        self.assertIn("ACT ONE", typst)
        self.assertIn("ACT TWO", typst)
        self.assertNotIn("#sp-act[\nTWO", typst)

    def test_a_forced_page_break_becomes_a_typst_page_break(self):
        with open(os.path.join(self.cwd, "work", "act-2.md"), "w", encoding="utf-8") as fh:
            fh.write("One.\n\n===\n\nTwo.\n")
        self.assertIn("#pagebreak()", self.typst(["work/act-2.md"]))

    def test_review_focus_the_title_page_survives_special_characters(self):
        title = 'A & B #1 — "Q" café'
        self.build(["work/act-1.md"], title=title, author="Zoë & Co", based_on="Based on $5 and @x",
                   contact="a@b.example", draft="Draft #2")
        with zipfile.ZipFile(os.path.join(self.cwd, "output/tb.epub")) as z:
            text = "\n".join(z.read(n).decode("utf-8") for n in z.namelist() if n.endswith(".xhtml"))
        self.assertIn("A &amp; B #1", text)
        self.assertIn("café", text)
        self.assertIn("Zoë &amp; Co", text)
        self.assertIn("Based on $5 and @x", text)          # the title lines pandoc's own title page omits
        self.assertIn("Draft #2", text)
        self.assertIn("a@b.example", text)

    def test_review_focus_the_epub_contents_have_no_stray_entry(self):
        import re
        self.build(["work/act-1.md", "work/act-2.md"])
        with zipfile.ZipFile(os.path.join(self.cwd, "output/tb.epub")) as z:
            nav = z.read("EPUB/nav.xhtml").decode("utf-8")
            pages = [z.read(n).decode("utf-8") for n in z.namelist() if n.startswith("EPUB/text/ch")]
        self.assertEqual(re.findall(r'<a href="[^"]*"[^>]*>([^<]*)</a>', nav), ["Title Page"])
        text = "\n".join(pages)
        for cls in ("scene-heading", "action", "character", "parenthetical", "dialogue", "transition", "centered"):
            self.assertIn(f'class="{cls}"', text, cls)
        self.assertIn('id="script"', text)

    def test_the_epub_stylesheet_hides_the_unlisted_heading_and_styles_the_classes(self):
        with open(os.path.join(PUBLISH_DIR, "screenplay", "screenplay.css"), encoding="utf-8") as fh:
            css = fh.read()
        self.assertIn("#script > h1 { display: none; }", css)
        for cls in ("scene-heading", "character", "dialogue", "parenthetical", "transition", "centered", "act-marker",
                    "title-line"):
            self.assertIn(f"div.{cls}", css)


class TemplateText(unittest.TestCase):
    def read(self, name):
        with open(os.path.join(PUBLISH_DIR, "screenplay", name), encoding="utf-8") as fh:
            return fh.read()

    def test_the_layout_functions_exist_and_the_numbering_is_set_up(self):
        t = self.read("screenplay.typ")
        for fn in ("sp-heading", "sp-action", "sp-character", "sp-parenthetical", "sp-dialogue", "sp-transition",
                   "sp-centered", "sp-act"):
            self.assertIn(f"#let {fn}(body)", t)
        self.assertIn('"Courier Prime", "Courier New", "DejaVu Sans Mono"', t)
        self.assertIn("margin: (left: 1.5in, right: 1in, top: 1in, bottom: 1in)", t)
        self.assertIn("#counter(page).update(0)", t)                  # the script's first page is page 1
        self.assertIn('display("1.")', t)

    def test_character_cues_and_headings_stay_with_what_follows(self):
        t = self.read("screenplay.typ")
        for fn in ("sp-heading", "sp-character", "sp-parenthetical"):
            line = next(l for l in t.split("\n") if l.startswith(f"#let {fn}("))
            self.assertIn("sticky: true", line, fn)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m unittest discover -s plugins/wrist/tests -p test_screenplay_publish.py 2>&1 | tail -4`
Expected: FAILED/ERROR (`wrist_publish.style_for` and `plan_screenplay` do not exist; the template files do not exist).

- [ ] **Step 3: Write the filter, the template and the stylesheet**

Create `plugins/wrist/skills/wrist/publish/screenplay/screenplay.lua`:

```lua
-- Turns the reader's classed Divs into calls of the layout functions in screenplay.typ for the PDF.
-- For every other format (the EPUB) the Divs stay as they are and the stylesheet styles their classes.
local KINDS = {
  ["scene-heading"] = "sp-heading", action = "sp-action", character = "sp-character",
  dialogue = "sp-dialogue", parenthetical = "sp-parenthetical", transition = "sp-transition",
  centered = "sp-centered", ["act-marker"] = "sp-act",
}

function Pandoc(doc)
  if not FORMAT:match("typst") then
    -- Without a heading before the script pandoc files it under the title and lists that in the contents.
    -- Give it an unlisted heading of its own; the stylesheet hides it.
    local out = {pandoc.Header(1, {pandoc.Str("Screenplay")}, pandoc.Attr("script", {"unlisted", "unnumbered"}))}
    -- The title page lines pandoc's own title page does not show.
    for _, key in ipairs({"based_on", "draft", "contact"}) do
      local v = doc.meta[key]
      if v and pandoc.utils.stringify(v) ~= "" then
        out[#out + 1] = pandoc.Div({pandoc.Para({pandoc.Str(pandoc.utils.stringify(v))})}, pandoc.Attr("", {"title-line"}))
      end
    end
    for _, b in ipairs(doc.blocks) do out[#out + 1] = b end
    doc.blocks = out
    return doc
  end
  local out = {}
  for _, b in ipairs(doc.blocks) do
    local class = b.t == "Div" and b.classes[1]
    if class == "pagebreak" then
      out[#out + 1] = pandoc.RawBlock("typst", "#pagebreak()")
    elseif class and KINDS[class] then
      out[#out + 1] = pandoc.RawBlock("typst", "#" .. KINDS[class] .. "[")
      for _, inner in ipairs(b.content) do out[#out + 1] = inner end
      out[#out + 1] = pandoc.RawBlock("typst", "]")
    else
      out[#out + 1] = b
    end
  end
  doc.blocks = out
  return doc
end
```

Create `plugins/wrist/skills/wrist/publish/screenplay/screenplay.typ`:

```typst
// wrist screenplay template for `pandoc --pdf-engine=typst`. US letter (or the trim size), 12 pt
// monospace, about 55 lines and about a minute a page. Needs typst 0.12 or later.
#set document(title: [$title$])
#set text(
  font: ($if(mainfont)$"$mainfont$", $endif$"Courier Prime", "Courier New", "DejaVu Sans Mono"),
  size: 12pt,
  lang: "$if(lang)$$lang$$else$en$endif$",
  top-edge: 0.8em,
  bottom-edge: -0.2em,
)
#set par(leading: 0pt, spacing: 0pt, justify: false)
#show strong: set text(weight: "bold")

#let sp-heading(body) = block(above: 24pt, below: 0pt, sticky: true, width: 100%)[#strong(upper(body))]
#let sp-action(body) = block(above: 12pt, below: 0pt, width: 100%)[#body]
#let sp-character(body) = block(above: 12pt, below: 0pt, sticky: true, width: 100%, inset: (left: 2.2in))[#upper(body)]
#let sp-parenthetical(body) = block(above: 0pt, below: 0pt, sticky: true, width: 100%, inset: (left: 1.6in, right: 2.0in))[#body]
#let sp-dialogue(body) = block(above: 0pt, below: 0pt, width: 100%, inset: (left: 1.0in, right: 1.5in))[#body]
#let sp-transition(body) = block(above: 12pt, below: 0pt, width: 100%)[#align(right)[#upper(body)]]
#let sp-centered(body) = block(above: 12pt, below: 0pt, width: 100%)[#align(center)[#body]]
#let sp-act(body) = {
  pagebreak(weak: true)
  align(center)[#strong(upper(body))]
  v(24pt)
}

// Title page: no number.
#page(paper: "$if(papersize)$$papersize$$else$us-letter$endif$", margin: (left: 1.5in, right: 1in, top: 1in, bottom: 1in),
      numbering: none, header: none)[
  #v(3in)
  #align(center)[
    #strong(upper[$title$])
    #v(2em)
    Written by
    #v(1em)
    $for(author)$$author$$sep$, $endfor$
    $if(based_on)$
    #v(3em)
    $based_on$
    $endif$
  ]
  $if(contact)$
  #place(bottom + left)[$contact$]
  $endif$
  $if(draft)$
  #place(bottom + right)[$draft$]
  $endif$
  #counter(page).update(0)
]

#set page(
  paper: "$if(papersize)$$papersize$$else$us-letter$endif$",
  margin: (left: 1.5in, right: 1in, top: 1in, bottom: 1in),
  header: context {
    // The first script page carries no number; later pages show it top right as "2."
    if counter(page).get().first() > 1 { align(right)[#counter(page).display("1.")] }
  },
  header-ascent: 50%,
)

$body$
```

Create `plugins/wrist/skills/wrist/publish/screenplay/screenplay.css`:

```css
body { font-family: "Courier Prime", "Courier New", Courier, monospace; font-size: 1em; line-height: 1.25; margin: 0 8%; }
div.scene-heading { font-weight: bold; text-transform: uppercase; margin: 2em 0 0.5em; }
div.action { margin: 1em 0 0; }
div.character { margin: 1em 0 0 35%; text-transform: uppercase; }
div.parenthetical { margin: 0 0 0 28%; }
div.dialogue { margin: 0 20% 0 18%; }
div.transition { margin: 1em 0 0; text-align: right; text-transform: uppercase; }
div.centered { margin: 1em 0 0; text-align: center; }
div.act-marker { margin: 3em 0 1em; text-align: center; font-weight: bold; text-transform: uppercase; page-break-before: always; }
div.pagebreak { page-break-after: always; }
div p { margin: 0; text-indent: 0; text-align: left; }
#script > h1 { display: none; }
div.title-line { margin: 0.5em 0; text-align: center; }
```

- [ ] **Step 4: Add the style helpers to `wrist_publish.py`**

Append to `plugins/wrist/skills/wrist/scripts/wrist_publish.py` (after `remove_marker`):

```python
STYLES = ("story", "book", "screenplay")
NUMBER_WORDS = ("ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN")
SCREENPLAY_KEYS = ("based_on", "draft", "contact")


def style_for(profile):
    """The publishing style: the profile's own, else `book` when it has a sequence function, else `story`."""
    style = getattr(profile, "publish_style", None)
    if style is None:
        return "book" if any(spec["sequence"] for spec in profile.functions.values()) else "story"
    if style not in STYLES:
        raise PublishError(f"unknown publishing style '{style}' (known: {', '.join(STYLES)})")
    return style


def with_act_markers(sources, act_files, out_dir, cwd):
    """The pandoc inputs with a one-line marker file before each act file, so the script can print
    ACT ONE, ACT TWO... Returns (inputs, marker paths)."""
    markers, inputs = [], []
    os.makedirs(os.path.join(cwd, out_dir), exist_ok=True)
    for source in sources:
        if source in act_files:
            n = act_files.index(source)
            marker = f"{out_dir}/.wrist-act-{n + 1}.md"
            with open(os.path.join(cwd, marker), "w", encoding="utf-8") as fh:
                fh.write(f"@@ACT {NUMBER_WORDS[n]}@@\n")
            markers.append(marker)
            inputs.append(marker)
        inputs.append(source)
    return inputs, markers


def remove_markers(markers, cwd):
    for marker in markers:
        remove_marker(marker, cwd)


def plan_screenplay(inputs, meta, out_dir, slug, publish_dir):
    """[(kind, argv)] for a screenplay: Fountain read by the custom reader, the Typst filter for the PDF.
    `meta` has title, author, optional language, trim, font, based_on, draft and contact."""
    folder = os.path.join(publish_dir, "screenplay")
    common = ["pandoc", "--from", os.path.join(folder, "fountain.lua"), *inputs,
              "--metadata", f"title={meta['title']}",
              "--metadata", f"author={meta['author']}",
              "--metadata", f"lang={meta.get('language') or 'en'}"]
    for key in SCREENPLAY_KEYS:
        if meta.get(key):
            common += ["--metadata", f"{key}={meta[key]}"]
    filt = ["--lua-filter", os.path.join(folder, "screenplay.lua")]
    epub = common + ["--to", "epub3", "--css", os.path.join(folder, "screenplay.css")] + filt \
        + ["-o", f"{out_dir}/{slug}.epub"]
    pdf = common + filt + ["--template", os.path.join(folder, "screenplay.typ"), "--pdf-engine=typst"]
    if meta.get("trim"):
        pdf += ["-V", f"papersize={meta['trim']}"]
    if meta.get("font"):
        pdf += ["-V", f"mainfont={meta['font']}"]
    pdf += ["-o", f"{out_dir}/{slug}.pdf"]
    return [("epub", epub), ("pdf", pdf)]
```

- [ ] **Step 5: Update `cmd_publish`**

In `wrist_check.py`, replace everything in `cmd_publish` after the line `    wrist_root, files, profile, pm, slug = load_all(args)` up to and including the final `    return 0` of that function with:

```python
    root = project_root(args)
    try:
        style = wrist_publish.style_for(profile)
    except wrist_publish.PublishError as exc:
        print(f"publish failed: {exc}")
        return 1
    expected = profile.expected_files(slug)
    sources = [path for path, function in expected if profile.functions[function]["prose"]]
    sequence_files = [path for path, function in expected if profile.functions[function]["sequence"]]
    meta = {"title": pm.front["title"][1], "author": pm.front["author"][1],
            "language": pm.front.get("language", (0, "en"))[1], "trim": pm.front.get("trim", (0, ""))[1],
            "font": pm.front.get("font", (0, ""))[1], "title_page": profile.title_page}
    markers = []
    if style == "screenplay":
        for key in wrist_publish.SCREENPLAY_KEYS:
            meta[key] = pm.front.get(key, (0, ""))[1]
        inputs = list(sources)
        if profile.options.get("act_headings"):
            inputs, markers = wrist_publish.with_act_markers(sources, sequence_files, "output", root)
        plan = wrist_publish.plan_screenplay(inputs, meta, "output", slug, PUBLISH_DIR)
    else:
        first_body = sequence_files[0] if style == "book" and sequence_files else None
        meta["front_matter"] = style == "book"
        for key in wrist_publish.FRONT_KEYS:
            meta[key] = pm.front.get(key, (0, ""))[1]
        inputs, marker = wrist_publish.with_marker(sources, first_body, "output", root)
        markers = [marker] if marker else []
        plan = wrist_publish.plan_commands(inputs, meta, "output", slug, PUBLISH_DIR)
    try:
        wrist_publish.run_commands(plan, root)
    except wrist_publish.PublishError as exc:
        print(f"publish failed: {exc}")
        return 1
    finally:
        wrist_publish.remove_markers(markers, root)
    print(f"published output/{slug}.epub and output/{slug}.pdf")
    return 0
```

- [ ] **Step 6: Run the tests, then look at a rendered page**

Run: `python3 -m unittest discover -s plugins/wrist/tests -q 2>&1 | tail -6`
Expected: `OK`.

Then build a longer script and look at it (the test suite cannot):

```bash
S=/tmp/claude-1000/-home-sean-Data-Projects-claude-plugins/b823c3ae-57a6-454b-b3b3-63ef3fa1a7f8/scratchpad
rm -rf $S/spcheck && mkdir -p $S/spcheck/work && cd $S/spcheck
python3 - <<'EOF'
scenes = "\n".join(f"INT. CABIN {i} - NIGHT\n\nMARIT checks the clipboard and finds the same number again, and the cabin hums around her.\n\nMARIT\nStill twenty-three.\n\nHALLORAN (O.S.)\n(from the wheelhouse)\nLog says twenty-four, and I have no reason to doubt the log.\n" for i in range(1, 17))
open("work/act-1.md", "w").write("INT. FERRY DECK - NIGHT\n\nMARIT counts faces.\n\nCUT TO:\n\n" + scenes)
open("work/act-2.md", "w").write("EXT. SEA GATE - DUSK\n\nThe gate stands open.\n\n> THE END <\n")
EOF
python3 - <<EOF
import sys; sys.path.insert(0, "/home/sean/Data/Projects/claude-plugins/plugins/wrist/skills/wrist/scripts")
import wrist_publish as w
inputs, markers = w.with_act_markers(["work/act-1.md", "work/act-2.md"], ["work/act-1.md", "work/act-2.md"], "output", ".")
w.run_commands(w.plan_screenplay(inputs, {"title": "The Third Bell", "author": "Sam Rivers", "based_on": "Based on a short story", "contact": "sam@example.com", "draft": "First draft, Oct 2026"}, "output", "tb", "/home/sean/Data/Projects/claude-plugins/plugins/wrist/skills/wrist/publish"), ".")
EOF
$S/venv/bin/python - <<'EOF'
import pymupdf
d = pymupdf.open("output/tb.pdf"); print(len(d), "pages", d[0].rect)
print([p.get_text().strip().split("\n")[0][:12] for p in d])
w, h = d[0].rect.width * 0.55, d[0].rect.height * 0.55
sheet = pymupdf.open(); page = sheet.new_page(width=w * 4, height=h)
for k, i in enumerate((0, 1, 2, len(d) - 1)): page.show_pdf_page(pymupdf.Rect(k * w, 0, (k + 1) * w, h), d, i)
page.get_pixmap(dpi=100).save("output/sheet.png")
EOF
```

Open `output/sheet.png` and confirm: the title page has the title centered about a third down, "Written by", the author, `based_on` below, `contact` at the foot left and `draft` at the foot right, and no number; the first script page has no number; later pages show "2.", "3." top right; scene headings bold, character cues indented further than dialogue, parentheticals between them, the transition at the right margin; the page that begins act two starts with a centered "ACT TWO". Fix `screenplay.typ` for anything wrong, then rerun the suite.

- [ ] **Step 7: Commit**

```bash
git add -A plugins/wrist
git commit -m "feat(wrist): publish a screenplay in screenplay layout" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 4: The screenplay profile data

**Files:**
- Create: `plugins/wrist/skills/wrist/profiles/screenplay/profile.json`, `questions.md`, `structures.md`, `quality.md`, `lint.json`
- Create: `plugins/wrist/tests/test_screenplay.py` (the `ScreenplayProfile` and `ScreenplayContent` classes)

**Interfaces:**
- Consumes: Tasks 1 to 3.
- Produces: profile `screenplay`. Question ids (exact): required `genre, premise, ending, tone, audience, format, runtime, acts, story`; deferrable `setting, locations, themes, comps, characters, events, fixed, structure, avoid, act_headings`. (Ids use a hyphen-free form for keys that are also premise keys: `acts` and `act_headings` are the keys; `QUESTION_RE` allows only lower-case words joined by hyphens, so the id is written `act-headings` in `questions.md`, and the premise key is `act_headings`; the checker matches an id to a key by replacing hyphens with underscores — see Step 3.) Premise keys `acts` (int 1–7, required), `act_headings` (bool). Functions as in the spec table. `lint.json` uses `action`/`dialogue`/`anywhere` scopes.

- [ ] **Step 1: Make question ids match underscore premise keys**

`QUESTION_RE` only allows hyphens, while premise keys are validated as `[a-z][a-z0-9-]*` (`NAME_RE`) and `META_RE` reads front matter keys as `[A-Za-z_]+`: a hyphenated key can never be read from `PREMISE.md`. So the key must be written `act_headings`, and `NAME_RE` must accept underscores for premise key names. Write the failing test first, in `plugins/wrist/tests/test_screenplay_engine.py`, appended before `if __name__ == "__main__":`:

```python
class UnderscoredKeys(unittest.TestCase):
    def test_a_premise_key_may_contain_underscores(self):
        data = base(premise_keys={"act_headings": {"type": "bool"}},
                    files=[{"path": "a.md", "function": "a", "order": 1, "when": "act_headings"}])
        p = wp.parse_profile(data)
        p.set_premise({"act_headings": "yes"})
        self.assertEqual([path for path, _ in p.expected_files("s")], ["a.md"])

    def test_a_question_id_matches_a_premise_key_with_hyphens_or_underscores(self):
        data = base(premise_keys={"act_headings": {"type": "bool"}})
        p = wp.parse_profile(data, "- [deferrable] act-headings: Should acts be labelled?\n")
        self.assertEqual([q.id for q in p.questions], ["act-headings"])
        self.assertEqual(p.question_key("act-headings"), "act_headings")
        self.assertIsNone(p.question_key("genre"))
```

Run: `python3 -m unittest discover -s plugins/wrist/tests -p test_screenplay_engine.py 2>&1 | tail -3` — expect FAILED.

Then edit `wrist_profile.py`: in `_validate_premise_keys` replace the `NAME_RE.match(kname)` test with a new `KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")` (define it next to `NAME_RE`), and add this method to `Profile`:

```python
    def question_key(self, qid):
        """The premise key a question id stands for (hyphens read as underscores), or None."""
        key = qid.replace("-", "_")
        return key if key in self.premise_keys else None
```

In `wrist_check.py` `premise_problems`, make this edit:

```bash
cd /home/sean/Data/Projects/claude-plugins/plugins/wrist/skills/wrist/scripts && python3 - <<'PYEOF'
s = open("wrist_check.py", encoding="utf-8").read()
old = """        if q.id in profile.premise_keys and pm.front.get(q.id, (0, ""))[1]:
            continue"""
new = """        key = profile.question_key(q.id)
        if key and pm.front.get(key, (0, ""))[1]:
            continue"""
assert old in s
open("wrist_check.py", "w", encoding="utf-8").write(s.replace(old, new, 1))
PYEOF
```

Run the engine tests and the full suite: expect `OK`.

- [ ] **Step 2: Write the failing profile tests**

Create `plugins/wrist/tests/test_screenplay.py`:

```python
import os
import re
import unittest

from support import SKILL

import wrist_profile as wp


class ScreenplayProfile(unittest.TestCase):
    def setUp(self):
        self.p = wp.load_profile("screenplay")
        self.p.set_premise({"acts": "3", "act_headings": "no"})

    def test_file_shape(self):
        self.assertEqual([path for path, _ in self.p.expected_files("the-third-bell")],
                         ["synopsis.md", "outline.md", "character.md", "misc.md",
                          "work/act-1.md", "work/act-2.md", "work/act-3.md"])

    def test_premise_keys(self):
        self.assertEqual(self.p.premise_keys["acts"], {"type": "int", "min": 1, "max": 7, "required": True})
        self.assertEqual(self.p.premise_keys["act_headings"]["type"], "bool")

    def test_a_screenplay_has_a_title_page_fountain_lint_and_its_own_style(self):
        self.assertIs(self.p.title_page, True)
        self.assertEqual(self.p.lint_format, "fountain")
        self.assertEqual(self.p.publish_style, "screenplay")

    def test_acts_are_a_sequence_with_established_and_no_printed_heading(self):
        spec = self.p.functions["act"]
        self.assertTrue(spec["sequence"])
        self.assertTrue(spec["prose"])
        self.assertEqual(spec["required_when_realized"], ["Established"])
        self.assertIsNone(spec["heading_field"])
        self.assertEqual(spec["fields"], ["Pages"])
        self.assertEqual(spec["children"]["scene"], ["Purpose", "Location", "Pages", "Must include", "Must avoid"])

    def test_the_registries(self):
        self.assertEqual(self.p.functions["outline"]["children"]["beat"], ["Purpose", "Change", "Pages"])
        self.assertEqual(self.p.functions["misc"]["children"]["location"], ["Slug", "Facts"])
        for kind in ("prop", "concept", "timeline"):
            self.assertEqual(self.p.functions["misc"]["children"][kind], ["Facts"])

    def test_only_the_acts_are_prose(self):
        self.assertEqual([n for n, s in self.p.functions.items() if s["prose"]], ["act"])

    def test_questions(self):
        required = {q.id for q in self.p.questions if q.required}
        self.assertEqual(required, {"genre", "premise", "ending", "tone", "audience", "format", "runtime", "acts",
                                    "story"})
        deferrable = {q.id for q in self.p.questions if not q.required}
        self.assertEqual(deferrable, {"setting", "locations", "themes", "comps", "characters", "events", "fixed",
                                      "structure", "avoid", "act-headings"})

    def test_every_premise_key_has_a_question(self):
        self.assertEqual({self.p.question_key(q.id) for q in self.p.questions} - {None}, set(self.p.premise_keys))


class ScreenplayContent(unittest.TestCase):
    def read(self, name):
        with open(os.path.join(SKILL, "profiles", "screenplay", name), encoding="utf-8") as fh:
            return fh.read()

    def test_structures(self):
        text = self.read("structures.md")
        for name in ("Aristotle", "Syd Field", "Hero's Journey", "Save the Cat!", "Sequence approach",
                     "Story Circle", "22 steps", "Kishōtenketsu"):
            self.assertIn(name, text)
        sections = text.split("\n## ")[1:]
        for section in sections:
            title = section.split("\n")[0]
            if title.startswith("Formats"):
                continue
            self.assertIn("**Best for:**", section, title)
            self.assertIn("**Pages in a 120-page feature:**", section, title)
            self.assertIn("**Pages in a 10-page short:**", section, title)

    def test_the_format_table(self):
        text = self.read("structures.md")
        for needle in ("feature", "short", "TV-style", "act_headings"):
            self.assertIn(needle, text)

    def test_quality_has_its_parts(self):
        text = self.read("quality.md")
        for heading in ("## Clichés and stock moves", "## Marks of low quality", "## Judgment checklist"):
            self.assertIn(heading, text)
        self.assertGreaterEqual(text.count("- [ ] "), 14)
        for phrase in ("runtime", "slug line", "Established", "subtext"):
            self.assertIn(phrase, text)

    def test_every_lint_pattern_matches_its_positive_and_not_its_negative(self):
        items = wp.load_profile("screenplay").lint_items()
        self.assertGreaterEqual(len(items), 16)
        ids = [i["id"] for i in items]
        self.assertEqual(len(ids), len(set(ids)))
        for item in items:
            with self.subTest(item["id"]):
                rx = re.compile(item["pattern"], re.IGNORECASE)
                self.assertTrue(rx.search(item["positive"]), "positive sample does not match")
                self.assertFalse(rx.search(item["negative"]), "negative sample matches")

    def test_lint_scopes_are_fountain_scopes(self):
        scopes = {i["scope"] for i in wp.load_profile("screenplay").lint_items()}
        self.assertEqual(scopes, {"action", "dialogue", "anywhere"})


if __name__ == "__main__":
    unittest.main()
```

Run: `python3 -m unittest discover -s plugins/wrist/tests -p test_screenplay.py 2>&1 | tail -3` — expect FAILED (`no profile 'screenplay'`).

- [ ] **Step 3: Write `profile.json`**

Create `plugins/wrist/skills/wrist/profiles/screenplay/profile.json`:

```json
{
  "name": "screenplay",
  "title_page": true,
  "publish": {"style": "screenplay"},
  "lint_format": "fountain",
  "premise_keys": {
    "acts": {"type": "int", "min": 1, "max": 7, "required": true},
    "act_headings": {"type": "bool"}
  },
  "files": [
    {"path": "synopsis.md", "function": "synopsis", "order": 1},
    {"path": "outline.md", "function": "outline", "order": 2},
    {"path": "character.md", "function": "characters", "order": 3},
    {"path": "misc.md", "function": "misc", "order": 4},
    {"path": "work/act-{n}.md", "function": "act", "order": 5, "family": "acts"}
  ],
  "functions": {
    "synopsis": {"heading": "synopsis", "fields": ["Logline", "Ending", "Theme"]},
    "outline": {
      "heading": "outline",
      "fields": ["Structure"],
      "children": {"beat": ["Purpose", "Change", "Pages"]}
    },
    "characters": {
      "heading": "characters",
      "children": {"character": ["Wants", "Flaw", "Voice", "Arc"]}
    },
    "misc": {
      "heading": "misc",
      "children": {"location": ["Slug", "Facts"], "prop": ["Facts"], "concept": ["Facts"], "timeline": ["Facts"]}
    },
    "act": {
      "heading": "act",
      "fields": ["Pages"],
      "required_when_realized": ["Established"],
      "sequence": true,
      "children": {"scene": ["Purpose", "Location", "Pages", "Must include", "Must avoid"]},
      "prose": true
    }
  },
  "relations": ["appears", "mentions", "sets up", "pays off", "realizes", "continues"],
  "limits": {"max_prose_words": 120}
}
```

- [ ] **Step 4: Write `questions.md`**

Create `plugins/wrist/skills/wrist/profiles/screenplay/questions.md`:

```markdown
# Premise questions: screenplay

Ask these in the premise phase, a few at a time, in plain language. A `required` question must be answered or
recorded as an `*UNKNOWN*:` before generation; a `deferrable` question may be left out (write `none (skipped on
purpose)` so `check` stops warning about it). The id is the key used in `wrist/PREMISE.md`.

Two answers decide which files exist, so they go in the `PREMISE.md` front matter as well: `acts` (a whole number,
1 to 7) and `act_headings` (`yes` or `no`). A question whose id is one of these keys counts as answered when the
front matter has the key (the id `act-headings` stands for the key `act_headings`). Changing either later means
changing the tree.

## The film

- [required] genre: What is the genre or blend of genres (drama, comedy, thriller, horror, science fiction, romance, crime, animation, documentary-style)?
- [required] premise: What is the central situation, or the question the film turns on, in a paragraph?
- [required] ending: What shape should the ending take (closed, open, ironic, reversal, bittersweet, a final image that answers the opening)?
- [required] tone: What tone should the film hold, and where, if anywhere, may it shift?
- [required] story: Whose story is it, and what do they want? (The protagonist and the want that drives the script.)
- [deferrable] themes: What is the film about underneath the plot?

## The audience and the form

- [required] audience: Who is it for, including the rating it aims at (G, PG, PG-13, R, or the equivalent)?
- [required] format: Is it a feature, a short, or something else (a pilot, a stage-length piece)?
- [required] runtime: How long should it run, in minutes? A page is about a minute.
- [required] acts: How many acts? If you are not sure, I will propose a count from the runtime and the structure (a feature is usually three or four, a short one to three); the number is then fixed for the tree.
- [deferrable] act-headings: Should the script print ACT ONE-style headings? A feature does not; a TV-style or stage script does. Answer `yes` or `no`.
- [deferrable] comps: Which films would sit next to this one?

## The world and what you already know

- [deferrable] setting: Where and when does it take place?
- [deferrable] locations: Which locations must be used, and are there limits (a single location, a small budget, no visual effects)?
- [deferrable] characters: Which characters do you already want fixed, and what do you know about them?
- [deferrable] events: Which scenes or events must happen, and roughly where?
- [deferrable] fixed: Which lines, images or real details must appear exactly?
- [deferrable] structure: Do you have a structure in mind (see structures.md), or should one be proposed from the answers above?
- [deferrable] avoid: What do you want kept out (subjects, tropes, kinds of language)?
```

- [ ] **Step 5: Write `structures.md`**

Create `plugins/wrist/skills/wrist/profiles/screenplay/structures.md`:

```markdown
# Screenplay structures

Pick one from the premise answers (genre, runtime, tone, ending) and record the choice in the outline's `Structure:`
field. If the user did not name one, record it as an `*UNKNOWN*:` with your choice as `Proposed:`. Each section says what
the form is, where it fits, where its beats fall on the page count of a 120-page feature and of a 10-page short, what
the outline must hold, and what to watch for. A page is about a minute. Round a beat to the nearest scene boundary.

## Aristotle's five-act

Exposition, rising action, climax, falling action, resolution (the Freytag pyramid).

- **Best for:** tragedy, historical and literary drama, ensemble films, anything where consequence matters more than escalation.
- **Pages in a 120-page feature:** exposition 1-18, rising action 18-60, climax 60-72, falling action 72-102, resolution 102-120.
- **Pages in a 10-page short:** exposition 1-1.5, rising action 1.5-5, climax 5-6, falling action 6-8.5, resolution 8.5-10.
- **Outline asks for:** a climax that is a choice or a revelation, a falling action that carries consequences, a resolution short enough to feel earned.
- **Watch for:** an exposition that explains instead of starting; a falling action longer than the rising action.

## Syd Field's paradigm

Three acts of setup (about 25%), confrontation (50%) and resolution (25%), hinged by two plot points and a midpoint.

- **Best for:** mainstream features of 90 to 120 pages; a safe default when the premise is goal-driven.
- **Pages in a 120-page feature:** setup 1-30 with the inciting incident near page 10 and plot point one near 25-30, confrontation 30-90 with the midpoint near 60 and plot point two near 85-90, resolution 90-120.
- **Pages in a 10-page short:** setup 1-2.5, confrontation 2.5-7.5 with the midpoint near 5, resolution 7.5-10.
- **Outline asks for:** both plot points as events that change what the protagonist wants or does, and a midpoint that is a turn, not a pause.
- **Watch for:** a first act that takes a third of the script; plot points that happen to the hero instead of being caused by the hero.

## Hero's Journey

Twelve stages: ordinary world, call to adventure, refusal, meeting the mentor, crossing the threshold, tests and allies and enemies, approach, ordeal, reward, the road back, resurrection, return with the elixir.

- **Best for:** adventure, fantasy, science fiction, coming-of-age.
- **Pages in a 120-page feature:** ordinary world 1-10, threshold 25-30, ordeal 60, road back 90, resurrection 105, return 115-120.
- **Pages in a 10-page short:** ordinary world 1, threshold 2.5, ordeal 5, road back 7.5, return 9-10.
- **Outline asks for:** the ordeal as a real loss, and what the hero brings back that the ordinary world lacks.
- **Watch for:** a mentor who exists to die or explain; a chosen one with no cost.

## Save the Cat!

Fifteen beats: opening image, theme stated, set-up, catalyst, debate, break into two, B story, fun and games, midpoint, bad guys close in, all is lost, dark night of the soul, break into three, finale, final image.

- **Best for:** commercial features with a clear hero and a clear want: comedy, thriller, family, genre.
- **Pages in a 120-page feature:** opening image 1, theme stated 5, catalyst 12, break into two 25, midpoint 60, all is lost 85, break into three 95, finale 95-118, final image 120.
- **Pages in a 10-page short:** opening image 0.5, catalyst 1, break into two 2, midpoint 5, all is lost 7, finale 8-9.5, final image 10.
- **Outline asks for:** all fifteen beats named, the theme stated once, and the opening and final images as a pair that shows the change.
- **Watch for:** beats that are present but change nothing; a theme stated by every character.

## Sequence approach

Eight sequences of about 15 pages (12 to 15 minutes), each with its own tension and a mini-resolution, two in act one, four in act two, two in act three.

- **Best for:** features that sag in the middle; a way to build a second act out of four small movies.
- **Pages in a 120-page feature:** sequences 1-15, 15-30, 30-45, 45-60, 60-75, 75-90, 90-105, 105-120.
- **Pages in a 10-page short:** eight beats of about 1.25 pages: use four sequences of 2.5 pages instead.
- **Outline asks for:** each sequence's goal, its obstacle and how it ends by raising the next.
- **Watch for:** sequences that only repeat; a sequence with no question to carry the reader to the next.

## Story Circle

Eight steps: you (a character in a zone of comfort), need, go, search, find, take, return, change.

- **Best for:** character-led films, television-shaped stories, quiet dramas where change matters more than plot.
- **Pages in a 120-page feature:** you and need 1-15, go 15-30, search 30-60, find 60, take 60-90, return 90-110, change 110-120.
- **Pages in a 10-page short:** you and need 1-1.5, go 1.5-2.5, search 2.5-5, find 5, take 5-7.5, return 7.5-9, change 9-10.
- **Outline asks for:** the need stated early, the price paid at "take", and the change shown by contrast with step one.
- **Watch for:** a change the character announces rather than shows.

## Truby's 22 steps

Weakness and need, ghost, inciting event, desire, ally, opponent, fake-ally opponent, first revelation and decision, plan, opponent's plan and main counterattack, drive, attack by ally, apparent defeat, second revelation and decision, audience revelation, third revelation and decision, gate and gauntlet, battle, self-revelation, moral decision, new equilibrium.

- **Best for:** richly plotted features where the opponent matters as much as the hero: crime, thriller, drama.
- **Pages in a 120-page feature:** steps 1-4 in pages 1-25, steps 5-12 in 25-60, steps 13-17 in 60-90, steps 18-22 in 90-120.
- **Pages in a 10-page short:** compress to seven steps: weakness, desire, opponent, plan, apparent defeat, self-revelation, new equilibrium.
- **Outline asks for:** the opponent's plan written as carefully as the hero's, and the moral decision as the climax.
- **Watch for:** twenty-two steps for ten pages; an opponent who is only an obstacle.

## Kishōtenketsu

Four parts: introduction (ki), development (shō), a turn that recontextualizes (ten), and reconciliation (ketsu). No conflict is required.

- **Best for:** shorts and quiet, observational features; tone-led stories; stories about attention rather than action.
- **Pages in a 120-page feature:** ki 1-30, shō 30-60, ten 60-90, ketsu 90-120 (rare; keep each part a real movement).
- **Pages in a 10-page short:** ki 1-2.5, shō 2.5-5, ten 5-7.5, ketsu 7.5-10.
- **Outline asks for:** a third part that is genuinely unrelated on the surface, and a fourth that lets the audience hold all of it without explaining the link.
- **Watch for:** a twist that is only a surprise; a fourth part that explains the connection.

## Formats and acts

A starting point, never a rule.

| Format | Runtime | Acts | `act_headings` | Start from |
|---|---|---|---|---|
| feature | 90 to 120 minutes | 3 or 4 (act two split in two) | no | Syd Field, Save the Cat!, Sequence approach |
| short | 5 to 40 minutes | 1 to 3 | no | Story Circle, Kishōtenketsu, a compressed Syd Field |
| TV-style (an hour) | 45 to 60 minutes | 5 or 6 (teaser and acts) | yes | Aristotle's five-act, Fichtean-style crises |
```

(Write the heading as `## Kishōtenketsu` and the table cell as `Kishōtenketsu`, with the real "ō" character, not the `ō` escape shown above.)

- [ ] **Step 6: Write `quality.md`**

Create `plugins/wrist/skills/wrist/profiles/screenplay/quality.md`:

```markdown
# Quality for a screenplay

The target is a script an agent, a reader or a jury would stop for. These lists name what to avoid. Copy the ones that
apply into each stand-in's `Rules:` during generation; check the work against all of them during realization. The
searchable items are in `lint.json` (run `wrist_check.py lint`); the rest need a reader's judgment, per act and across
the whole script.

## Clichés and stock moves

Openings
- Waking up, an alarm clock, a mirror shot, a dream, a voice-over that explains the world, a sunrise.
- Opening on a flashback to the event that explains everything.
- A cold open that is only noise before the real film starts.

Description
- "We see", "we hear" and camera directions (PAN, ZOOM, CLOSE ON, ANGLE ON) in a spec script.
- What a character thinks, remembers, knows or decides, which the camera cannot show.
- Stock reactions: eyes widen, heart pounds, a single tear, a smirk, a sigh.
- Action blocks of five lines or more.

Dialogue
- On-the-nose lines that state the feeling ("I feel so alone").
- "As you know" exposition, and characters telling each other what both know.
- Stock lines: "We need to talk", "It's quiet. Too quiet."
- Every character speaking in the writer's voice.

Plot
- The mentor who dies so the hero grows, the villain who explains the plan, the last-second rescue.
- A coincidence that solves the problem.
- A final image that states the theme.

## Marks of low quality

- Pages over or under the runtime (a page is about a minute); a first act that takes a third of the script.
- An act turn that lands off its page (for a feature, the first turn near page 25 to 30, the midpoint near 60, the second turn near 85 to 90).
- Scenes that do not turn: nothing is different at the end of them.
- Dialogue with no subtext: every line says exactly what the character means.
- Unfilmable description; narration of thought in action lines.
- Slug lines that rename the same place (KITCHEN in one scene, THE KITCHEN in the next, CAMERON'S KITCHEN after that).
- A protagonist who makes no decision in the second act.
- Information delivered in dialogue instead of shown.
- Characters who are named but never matter; a cast of voices that sound alike.
- An ending that explains.

## Judgment checklist

Work through this in the review pass, with the realized Fountain and the stand-ins open. Do it once per act as you
finish it, and again for the whole script before `review_done: yes`. Mark an item only when you have checked it
against the text.

Per act
- [ ] The act's first scene belongs to this act and creates a question or a pressure.
- [ ] Every scene changes something: a fact, a relationship, a plan, a risk.
- [ ] Every scene heading uses a location's `Slug:` exactly as the misc stand-in writes it.
- [ ] Action blocks are four lines or fewer and describe only what the camera can see.
- [ ] Each speaker's lines sound different from the others'.
- [ ] No line states a feeling that an action or an image could carry; there is subtext.
- [ ] Every item in `Must include:` is present and no `Must avoid:` item appears.
- [ ] Nothing contradicts the `Established:` fields of earlier acts, unless a stand-in names the contradiction as deliberate.
- [ ] The act's `Established:` field lists every new fact, date, injury, prop and promise the text fixed.
- [ ] No fact appears in the text that no stand-in holds.

Whole script
- [ ] The page count is within about ten percent of the runtime.
- [ ] The act turns fall near the pages the structure gives them.
- [ ] Stakes escalate from act to act and are paid, not announced.
- [ ] The protagonist makes a costly decision in the second act.
- [ ] Setups are paid off and nothing is planted without a payoff.
- [ ] No coincidence solves the central problem.
- [ ] The final image answers the opening image and does not state the theme.
- [ ] `wrist_check.py lint` reports no hits, or every hit is deliberate.
```

- [ ] **Step 7: Write `lint.json`**

Create `plugins/wrist/skills/wrist/profiles/screenplay/lint.json`:

```json
{
  "items": [
    {"id": "we-see", "pattern": "\\bwe (?:see|hear|watch|notice)\\b", "label": "camera in the description",
     "note": "Describe what is on screen; the reader is not the camera.", "scope": "action",
     "positive": "We see a door open.", "negative": "She sees the door open."},
    {"id": "camera-direction", "pattern": "\\b(?:pans? (?:to|across|over)|zooms? (?:in|out)|tilts? (?:up|down)|close (?:up )?on|angle on|insert (?:shot|of)|camera (?:follows|pans|moves|zooms))\\b",
     "label": "camera direction", "note": "A spec script leaves shots to the director; write the image, not the lens.", "scope": "action",
     "positive": "CLOSE ON the letter.", "negative": "She closes the door."},
    {"id": "suddenly", "pattern": "\\bsuddenly\\b", "label": "intensifier",
     "note": "If it is sudden, the sentence can be.", "scope": "action",
     "positive": "Suddenly the door opens.", "negative": "The door opens."},
    {"id": "begins-to", "pattern": "\\b(?:begins?|starts?) to\\b", "label": "weak verb phrase",
     "note": "She cries, not begins to cry.", "scope": "action",
     "positive": "She begins to cry.", "negative": "She starts the engine."},
    {"id": "unfilmable", "pattern": "\\b(?:she|he|they) (?:thinks|remembers|realizes|realises|wonders|knows|wishes|feels like)\\b",
     "label": "unfilmable description", "note": "Show it as an action or cut it; the camera cannot see a thought.", "scope": "action",
     "positive": "She remembers her mother.", "negative": "She picks up the phone."},
    {"id": "smirk", "pattern": "\\bsmirk(?:s|ed|ing)?\\b", "label": "stock reaction",
     "note": "Describe the face or the choice.", "scope": "action",
     "positive": "He smirks.", "negative": "He smiles."},
    {"id": "sigh", "pattern": "\\bsighs?\\b", "label": "stock gesture",
     "note": "A stalling beat; replace it with an action.", "scope": "action",
     "positive": "She sighs.", "negative": "She signs the form."},
    {"id": "eyes-widen", "pattern": "\\beyes (?:widen|widened|go wide|went wide)\\b", "label": "stock reaction",
     "note": "Show the surprise in what the character does.", "scope": "action",
     "positive": "Her eyes widen.", "negative": "Her eyes are wide-set."},
    {"id": "heart-pounds", "pattern": "\\bheart (?:pounds?|pounded|races|raced|skips|skipped)\\b", "label": "stock reaction",
     "note": "Name what the body does that this scene alone would cause.", "scope": "action",
     "positive": "His heart pounds.", "negative": "The heart of the town is its clock."},
    {"id": "single-tear", "pattern": "\\b(?:a )?tears? (?:rolls?|streams?|falls?|runs?) down\\b", "label": "stock reaction",
     "note": "Let the audience supply the tear.", "scope": "action",
     "positive": "A tear rolls down her cheek.", "negative": "She rolls down the window."},
    {"id": "waking-up", "pattern": "\\b(?:wakes? up|alarm clock|jolts awake|bolts upright)\\b", "label": "stock opening",
     "note": "Waking up is the most common first scene there is.", "scope": "action",
     "positive": "She wakes up.", "negative": "She wakes the baby."},
    {"id": "mirror-shot", "pattern": "\\b(?:looks|stares|gazes) (?:at (?:herself|himself)|into the mirror)\\b", "label": "stock device",
     "note": "Introducing a character through a mirror is a well-known shortcut.", "scope": "action",
     "positive": "She stares into the mirror.", "negative": "She stares at the window."},
    {"id": "as-you-know", "pattern": "\\bas you know\\b", "label": "expository dialogue",
     "note": "Characters do not tell each other what both know.", "scope": "dialogue",
     "positive": "As you know, the gate closes at dusk.", "negative": "You know the way."},
    {"id": "need-to-talk", "pattern": "\\bwe need to talk\\b", "label": "stock line",
     "note": "Start the conversation; do not announce it.", "scope": "dialogue",
     "positive": "We need to talk.", "negative": "We need to leave."},
    {"id": "too-quiet", "pattern": "\\bit['\\u2019]?s (?:too )?quiet\\b", "label": "stock line",
     "note": "The quiet-before-the-storm line is a cliché.", "scope": "dialogue",
     "positive": "It's too quiet.", "negative": "It's a quiet street."},
    {"id": "on-the-nose", "pattern": "\\bI (?:feel|am feeling) (?:so |very )?(?:sad|angry|alone|scared|afraid|happy|lost)\\b",
     "label": "on-the-nose dialogue", "note": "Give the feeling an action or a subtext.", "scope": "dialogue",
     "positive": "I feel so alone.", "negative": "I feel the wall."},
    {"id": "beat", "pattern": "\\(beat\\)", "label": "stalling parenthetical",
     "note": "Write the pause into the action or the rhythm of the line.", "scope": "dialogue",
     "positive": "(beat)", "negative": "(quietly)"},
    {"id": "pregnant-pause", "pattern": "\\b(?:pregnant pause|deafening silence|silence was deafening)\\b", "label": "stock phrase",
     "note": "Describe what fills the silence.", "scope": "anywhere",
     "positive": "A pregnant pause.", "negative": "A long pause."}
  ]
}
```

- [ ] **Step 8: Run the tests and commit**

Run: `python3 -m unittest discover -s plugins/wrist/tests -q 2>&1 | tail -6`
Expected: `OK`. If a structure section lacks one of the three required bold labels, fix the section, not the test.

```bash
git add -A plugins/wrist
git commit -m "feat(wrist): add the screenplay profile data" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 5: The-third-bell example screenplay and its tests

**Files:**
- Create: `plugins/wrist/skills/wrist/assets/examples/the-third-bell/` (PREMISE, 7 stand-ins, 4 realized notes files, 3 Fountain acts, generated `.stamps`)
- Modify: `plugins/wrist/tests/support.py` (a `ScriptCase`)
- Modify: `plugins/wrist/tests/test_screenplay.py` (append `ThirdBell*` classes)

**Interfaces:**
- Consumes: Tasks 1 to 4.
- Produces: example project, slug `the-third-bell`, `acts: 3`, `act_headings: yes` (so the act markers are exercised), `draft:` and `contact:` set. Stand-ins: `synopsis.md`, `outline.md`, `character.md`, `misc.md`, `work/act-1.md`, `work/act-2.md`, `work/act-3.md` (7). Realized files for all seven, all stamped, every act with a filled `Established:`. The acts are real Fountain. It must pass `check` with 0 errors and 0 warnings, `lint` with 0 hits, and open all three gates. `support.py` adds `SCRIPT_EXAMPLE` (the path), `S_PREMISE`, `S_ACT1`, `S_ACT2`, `S_ACT3` (stand-in paths) and `class ScriptCase(TreeCase)` (copies the script example).

- [ ] **Step 1: Add `ScriptCase` and write the failing tests**

In `plugins/wrist/tests/support.py`, add after the `N_CHAPTER3` line:

```python
SCRIPT_EXAMPLE = os.path.join(SKILL, "assets", "examples", "the-third-bell")
S_PREMISE = "wrist/PREMISE.md"
S_ACT1 = "wrist/work/act-1.md.wrist.md"
S_ACT2 = "wrist/work/act-2.md.wrist.md"
S_ACT3 = "wrist/work/act-3.md.wrist.md"
```

and append at the end of the file:

```python


class ScriptCase(TreeCase):
    example = SCRIPT_EXAMPLE
```

Append to `plugins/wrist/tests/test_screenplay.py`, adding `import shutil`, `import subprocess`, `import zipfile` to the imports, and extending the `from support import SKILL` line to `from support import S_ACT1, S_ACT2, S_ACT3, S_PREMISE, SKILL, ScriptCase`:

```python
HAVE_TOOLS = shutil.which("pandoc") and shutil.which("typst")


class ThirdBellChecks(ScriptCase):
    def test_the_example_checks_clean(self):
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("7 stand-ins", out)
        self.assertIn("0 errors, 0 warnings", out)

    def test_every_gate_is_open(self):
        for phase in ("generation", "realization", "publishing"):
            code, out = self.run_wrist("gate", "wrist", phase)
            self.assertEqual(code, 0, out)

    def test_every_file_is_realized_and_lint_is_clean(self):
        _, out = self.run_wrist("status", "wrist")
        self.assertIn("Realized (7):", out)
        _, out = self.run_wrist("lint", "wrist")
        self.assertIn("0 hits in 0 files", out)

    def test_order_follows_the_profile(self):
        _, out = self.run_wrist("order", "wrist")
        names = [l.split()[1] for l in out.splitlines() if l[:1].isdigit()]
        self.assertEqual(names, ["synopsis.md", "outline.md", "character.md", "misc.md",
                                 "work/act-1.md", "work/act-2.md", "work/act-3.md"])

    def test_the_acts_are_real_fountain(self):
        import wrist_lint
        for n in (1, 2, 3):
            kinds = set(wrist_lint.elements(self.read(f"work/act-{n}.md")))
            self.assertLessEqual({"scene-heading", "action"}, kinds, n)
            if n < 3:                                   # act 3 is silent: the passenger never speaks
                self.assertLessEqual({"character", "dialogue"}, kinds, n)


class ThirdBellFileSet(ScriptCase):
    def test_review_focus_a_fourth_act_needs_its_stand_in(self):
        self.replace(S_PREMISE, "acts: 3", "acts: 4")
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("required stand-in missing: wrist/work/act-4.md.wrist.md", out)

    def test_review_focus_fewer_acts_leave_a_stand_in_outside_the_shape(self):
        self.replace(S_PREMISE, "acts: 3", "acts: 2")
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("outside the screenplay shape", out)

    def test_acts_out_of_range_or_missing_are_clear_errors(self):
        for value in ("0", "8", "three"):
            with self.subTest(value=value):
                self.replace(S_PREMISE, "acts: 3", f"acts: {value}")
                code, out = self.check()
                self.assertEqual(code, 1, out)
                self.assertIn("`acts:` must be a whole number from 1 to 7", out)
                self.assertIn(f"(got '{value}')", out)
                self.replace(S_PREMISE, f"acts: {value}", "acts: 3")
        self.replace(S_PREMISE, "acts: 3\n", "")
        code, out = self.check()
        self.assertIn("`acts:` is required (a whole number from 1 to 7)", out)

    def test_the_acts_and_act_headings_questions_are_answered_by_the_front_matter(self):
        code, out = self.check()
        self.assertNotIn("question 'acts'", out)
        self.assertNotIn("question 'act-headings'", out)


class ThirdBellContinuity(ScriptCase):
    def test_stamp_refuses_an_act_with_no_established_text(self):
        self.replace(S_ACT2, "- **Established:**", "- **Notes:**")
        code, out = self.run_wrist("stamp", "wrist", "work/act-2.md")
        self.assertEqual(code, 1, out)
        self.assertIn("no `Established:` text", out)

    def test_an_act_must_continue_the_one_before(self):
        self.replace(S_ACT3, "(continues)", "(mentions)")
        code, out = self.check()
        self.assertIn("no `Depends on:` link to work/act-2.md's stand-in with the relation `continues`", out)

    def test_editing_an_act_after_stamping_blocks_publishing(self):
        self.write("work/act-1.md", self.read("work/act-1.md") + "\nA stray line.\n")
        code, out = self.run_wrist("gate", "wrist", "publishing")
        self.assertIn("work/act-1.md is edited", out)

    def test_review_focus_lint_flags_a_cliche_in_action_but_not_the_same_words_in_dialogue(self):
        text = self.read("work/act-1.md")
        self.write("work/act-1.md", text + "\nMARIT\nWe see the problem, as you know.\n\nWe see a door open.\n")
        code, out = self.run_wrist("lint", "wrist")
        self.assertIn("[as-you-know]", out)
        self.assertIn("[we-see]", out)
        self.assertEqual(out.count("[we-see]"), 1)


class ThirdBellPublish(ScriptCase):
    @unittest.skipUnless(HAVE_TOOLS, "pandoc and typst are not installed")
    def test_the_example_publishes_with_act_headings(self):
        code, out = self.run_wrist("publish", "wrist")
        self.assertEqual(code, 0, out)
        with open(self.path("output/the-third-bell.pdf"), "rb") as fh:
            self.assertEqual(fh.read(5), b"%PDF-")
        with zipfile.ZipFile(self.path("output/the-third-bell.epub")) as z:
            text = "\n".join(z.read(n).decode("utf-8") for n in z.namelist() if n.endswith(".xhtml"))
        for needle in ("ACT ONE", "ACT TWO", "ACT THREE", "class=\"scene-heading\"", "class=\"character\""):
            self.assertIn(needle, text, needle)
        self.assertIn("First draft", text)
        self.assertEqual(sorted(os.listdir(self.path("output"))), ["the-third-bell.epub", "the-third-bell.pdf"])

    @unittest.skipUnless(HAVE_TOOLS, "pandoc and typst are not installed")
    def test_without_act_headings_the_epub_has_no_act_labels(self):
        self.replace(S_PREMISE, "act_headings: yes", "act_headings: no")
        code, out = self.run_wrist("publish", "wrist")
        self.assertEqual(code, 0, out)
        with zipfile.ZipFile(self.path("output/the-third-bell.epub")) as z:
            text = "\n".join(z.read(n).decode("utf-8") for n in z.namelist() if n.endswith(".xhtml"))
        self.assertNotIn("ACT ONE", text)

    @unittest.skipUnless(HAVE_TOOLS, "pandoc and typst are not installed")
    def test_a_failed_build_removes_the_act_markers(self):
        self.write("work/act-2.md", "INT. A - DAY\n\n\x00\x00\n")
        self.run_wrist("stamp", "wrist", "work/act-2.md")
        self.run_wrist("publish", "wrist")
        self.assertFalse([n for n in os.listdir(self.path("output")) if n.startswith(".wrist-act")]
                         if os.path.isdir(self.path("output")) else [])
```

Run: `python3 -m unittest discover -s plugins/wrist/tests -p test_screenplay.py 2>&1 | tail -4` — expect errors for `ThirdBell*` (the example does not exist).

- [ ] **Step 2: Write the premise and the registry stand-ins**

Create `.../the-third-bell/wrist/PREMISE.md`:

```markdown
---
profile: screenplay
title: The Third Bell
slug: the-third-bell
author: Ada Example
language: en
acts: 3
act_headings: yes
based_on: Based on a short story by Ada Example
draft: First draft, October 2026
contact: ada@example.com
questions_generation: done
questions_realization: done
questions_publishing: done
review_done: yes
---

# Premise

A worked example: a three-act short film of about six pages.

## Answers

- **genre:** Quiet suspense drama.
- **premise:** A ferry deckhand counts her passengers every night and one night the count is wrong in a way she cannot explain.
- **ending:** Open: she cannot tell whether the extra passenger is a person.
- **tone:** Dry and watchful, tightening toward the end.
- **story:** Marit, a deckhand who trusts her count above everything, who wants the number to be right.
- **audience:** Adult festival audience, PG-13.
- **format:** Short film.
- **runtime:** About six minutes.
- **themes:** Counting, trust, what we owe the unaccounted for.
- **comps:** None.
- **setting:** A small ferry in fog, present day.
- **locations:** Two: the ferry deck and the shore gate. No effects.
- **characters:** Marit, a deckhand; Halloran, the captain.
- **events:** The count is wrong; she recounts; she finds the extra passenger.
- **fixed:** The log says twenty-four.
- **structure:** Three-act, one act per page pair.
- **avoid:** Jump scares, a twist that the deckhand was dead all along.
```

Create `.../the-third-bell/wrist/synopsis.md.wrist.md`:

```markdown
# synopsis: The Third Bell

Notes for the one-paragraph synopsis of the film.

- **Logline:** A ferry deckhand who trusts her passenger count above everything finds it wrong by one, and must decide what to do about the extra.
- **Ending:** She writes the higher number in the log and the count comes out right.
- **Theme:** Counting is a way of owing.
- **Rules:** One paragraph, present tense, under 100 words, and it states the ending.
- **Required:** always
- **Depends on:** none
- **Unknowns:** none
```

Create `.../the-third-bell/wrist/outline.md.wrist.md`:

```markdown
# outline: The Third Bell

Notes for the outline of the film.

- **Structure:** Three-act, one act per two pages: the count, the recount, the log.
- **Rules:** Three beats only. Each beat changes what Marit will do next.
- **Required:** always
- **Depends on:** [synopsis](./synopsis.md.wrist.md) (mentions)
- **Unknowns:** none

## beat: The count

- **Purpose:** Establish Marit, the deck and the number.
- **Change:** The announced count is one higher than hers.
- **Pages:** 1-2

## beat: The recount

- **Purpose:** She proves the count and finds the footprints.
- **Change:** She stops arguing with the number.
- **Pages:** 3-4

## beat: The log

- **Purpose:** Resolve by action: she writes the higher number.
- **Change:** The count comes out right.
- **Pages:** 5-6
```

Create `.../the-third-bell/wrist/character.md.wrist.md`:

```markdown
# characters: The Third Bell

Notes for the registry of characters.

- **Rules:** Only Marit and Halloran are named; every other passenger is unnamed.
- **Required:** always
- **Depends on:** [synopsis](./synopsis.md.wrist.md) (mentions)
- **Unknowns:** none

## character: Marit

A ferry deckhand in her forties, twenty years on the water.

- **Wants:** The number to be right.
- **Flaw:** Trusts the count over her own eyes.
- **Voice:** Short, practical, never asks a question twice.
- **Arc:** From correcting the number to accepting it.

## character: Halloran

The captain, in the wheelhouse.

- **Wants:** To keep to the timetable.
- **Flaw:** Never looks up from the wheel.
- **Voice:** Flat, one line at a time.
- **Arc:** None; he is the constant.
```

Create `.../the-third-bell/wrist/misc.md.wrist.md`:

```markdown
# misc: The Third Bell

Notes for locations, props and the timeline.

- **Rules:** Only these entries; nothing else is named.
- **Required:** always
- **Depends on:** [synopsis](./synopsis.md.wrist.md) (mentions)
- **Unknowns:** none

## location: The ferry deck

- **Slug:** FERRY DECK
- **Facts:** An open deck with benches under a rail, in fog. The wheelhouse hatch is at one end.

## location: The shore gate

- **Slug:** SEA GATE
- **Facts:** A chain gate at the end of the crossing. It stands open on its chain.

## prop: The clipboard

- **Facts:** Marit's tally, in pencil, with the figure boxed.

## timeline: The crossing

- **Facts:** One crossing, about twenty minutes, at night.
```

- [ ] **Step 3: Write the act stand-ins**

Create `.../the-third-bell/wrist/work/act-1.md.wrist.md`:

```markdown
# act: The Count

Notes for act 1.

- **Pages:** 1-2
- **Established:** Marit counts twenty-three passengers on the ferry deck and boxes the figure on her clipboard. The speaker announces twenty-four. Halloran is in the wheelhouse and does not look up. The fog is heavy.
- **Required:** always
- **Rules:** Open on the count, not the weather. Marit never explains why she counts.
- **Depends on:** none
- **Unknowns:** none

## scene: On deck

- **Purpose:** Establish Marit, the clipboard and the wrong number.
- **Location:** FERRY DECK
- **Pages:** 1-2
- **Must include:** The clipboard; the boxed figure; the announcement of twenty-four; Halloran's silence.
- **Must avoid:** Backstory; naming a feeling.
- **Depends on:** [The count](../outline.md.wrist.md#beat-the-count) (realizes)
- **Depends on:** [Marit](../character.md.wrist.md#character-marit) (appears)
- **Depends on:** [Halloran](../character.md.wrist.md#character-halloran) (appears)
- **Depends on:** [The ferry deck](../misc.md.wrist.md#location-the-ferry-deck) (appears)
- **Depends on:** [The clipboard](../misc.md.wrist.md#prop-the-clipboard) (appears)
```

Create `.../the-third-bell/wrist/work/act-2.md.wrist.md`:

```markdown
# act: The Recount

Notes for act 2.

- **Pages:** 3-4
- **Established:** Marit recounts twice and gets twenty-three both times. She finds one set of wet footprints that runs straight to a seat. Halloran says only that the log says twenty-four.
- **Required:** always
- **Rules:** Dialogue stays short. No jump scare.
- **Depends on:** [The Count](./act-1.md.wrist.md) (continues)
- **Unknowns:** none

## scene: The recount

- **Purpose:** She proves the count and finds the footprints.
- **Location:** FERRY DECK
- **Pages:** 3-4
- **Must include:** Two recounts; the footprints; Halloran's one line.
- **Must avoid:** Explaining the footprints.
- **Depends on:** [The recount](../outline.md.wrist.md#beat-the-recount) (realizes)
- **Depends on:** [Marit](../character.md.wrist.md#character-marit) (appears)
- **Depends on:** [Halloran](../character.md.wrist.md#character-halloran) (appears)
- **Depends on:** [The ferry deck](../misc.md.wrist.md#location-the-ferry-deck) (appears)
- **Depends on:** [The clipboard](../misc.md.wrist.md#prop-the-clipboard) (appears)
```

Create `.../the-third-bell/wrist/work/act-3.md.wrist.md`:

```markdown
# act: The Log

Notes for act 3.

- **Pages:** 5-6
- **Established:** Marit follows the footprints and finds one dry passenger who does not speak. She erases twenty-three and writes twenty-four. The ferry reaches the sea gate and the chain stands open.
- **Required:** always
- **Rules:** End on an image, not on a statement.
- **Depends on:** [The Recount](./act-2.md.wrist.md) (continues)
- **Unknowns:** none

## scene: The log

- **Purpose:** Resolve by action: she writes the higher number.
- **Location:** SEA GATE
- **Pages:** 5-6
- **Must include:** The dry passenger; the erased figure; the open gate.
- **Must avoid:** The passenger speaking; a stated moral.
- **Depends on:** [The log](../outline.md.wrist.md#beat-the-log) (realizes)
- **Depends on:** [Marit](../character.md.wrist.md#character-marit) (appears)
- **Depends on:** [The shore gate](../misc.md.wrist.md#location-the-shore-gate) (appears)
- **Depends on:** [The clipboard](../misc.md.wrist.md#prop-the-clipboard) (appears)
```

- [ ] **Step 4: Add the backlinks and check**

Run:

```bash
cd /home/sean/Data/Projects/claude-plugins/plugins/wrist/skills/wrist/assets/examples/the-third-bell
S=../../../scripts/wrist_check.py
python3 $S fix-backlinks wrist --write | tail -3
python3 $S check wrist
```

Expected: `7 stand-ins, ... 0 errors, 0 warnings`. If `check` complains, fix the stand-in text and rerun. Because acts 2 and 3 and the registries have no hand-written `Referred by:`, `fix-backlinks` adds them; act 3 and act-1's own `Referred by:` may still be missing, so add `- **Referred by:** none` to `act-3`'s level-1 fields if `check` reports it.

- [ ] **Step 5: Write the realized files**

Create `.../the-third-bell/synopsis.md`:

```markdown
# The Third Bell: Synopsis

Marit, a ferry deckhand who trusts her passenger count above everything, finds it wrong by one on a foggy night crossing. She recounts, finds one set of wet footprints and one dry passenger who does not speak, and writes the higher number in the log. The count comes out right.
```

Create `.../the-third-bell/outline.md`:

```markdown
# The Third Bell: Outline

1. **The count (pages 1-2).** The announced count is one higher than Marit's.
2. **The recount (pages 3-4).** She proves the count and finds the footprints.
3. **The log (pages 5-6).** She writes the higher number and the count comes out right.
```

Create `.../the-third-bell/character.md`:

```markdown
# The Third Bell: Characters

**Marit.** A ferry deckhand in her forties, twenty years on the water. She wants the number to be right and trusts the count over her own eyes.

**Halloran.** The captain, in the wheelhouse. He wants to keep to the timetable and never looks up from the wheel.
```

Create `.../the-third-bell/misc.md`:

```markdown
# The Third Bell: Locations, Props and Timeline

**FERRY DECK.** An open deck with benches under a rail, in fog. The wheelhouse hatch is at one end.

**SEA GATE.** A chain gate at the end of the crossing. It stands open on its chain.

**The clipboard.** Marit's tally, in pencil, with the figure boxed.

**The crossing.** One crossing, about twenty minutes, at night.
```

Create `.../the-third-bell/work/act-1.md`:

```fountain
INT. FERRY DECK - NIGHT

Fog presses at the rail. MARIT (40s) walks the benches with a clipboard, touching each seatback as she counts. Passengers sit with their collars up.

MARIT
(under her breath)
Twenty-two. Twenty-three.

She boxes the figure in pencil. A speaker clicks over her head.

HALLORAN (V.O.)
Good evening. We have twenty-four passengers aboard.

Marit stops. She looks at the clipboard: 23, boxed. She looks up at the speaker, then at the wheelhouse hatch. Halloran's shape stands at the wheel and does not turn.
```

Create `.../the-third-bell/work/act-2.md`:

```fountain
INT. FERRY DECK - NIGHT

Marit counts again, slower, from the stern. Faces: a man with a bicycle, two women in work fleeces, a student with headphones around his neck. She touches each seatback.

MARIT
(whispering)
Twenty-three.

She counts a third time and gets the same number. The deck is slick with damp. She stops looking at the passengers and looks down.

One set of wet footprints crosses the deck. Everyone else's marks wander to the rail and back. These run straight.

Marit climbs to the wheelhouse hatch.

MARIT
You hear that count?

HALLORAN
Log says twenty-four.

He does not look at her. She goes back down.
```

Create `.../the-third-bell/work/act-3.md`:

```fountain
INT. FERRY DECK - NIGHT

The footprints end at the last bench by the window. Someone sits there, dry, hands folded, face hard to hold in the eye. Fog beads on the glass beside them and does not touch them.

Marit stands over the seat. The passenger turns toward her and waits. They do not speak.

She looks at the clipboard. She rubs out the boxed 23 with the heel of her pencil until the paper goes grey. She writes 24 and boxes it.

EXT. SEA GATE - DUSK

The ferry noses in. The chain across the gate lies slack on the stones. Beyond it the road goes on into fog.

> THE END <
```

(Note the last act opens with `INT.` and then `EXT.`; keep the single blank lines exactly as shown so the headings are recognised.)

- [ ] **Step 6: Stamp and verify the example**

Run:

```bash
cd /home/sean/Data/Projects/claude-plugins/plugins/wrist/skills/wrist/assets/examples/the-third-bell
S=../../../scripts/wrist_check.py
python3 $S stamp wrist --all | tail -2
for p in generation realization publishing; do python3 $S gate wrist $p; done
python3 $S check wrist | tail -1; python3 $S status wrist | head -1; python3 $S lint wrist | grep hits; python3 $S order wrist
```

Expected: `7 stamped`; three `open`; `7 stand-ins ... 0 errors, 0 warnings`; `Realized (7):`; `0 hits in 0 files`; the order synopsis, outline, character, misc, act-1, act-2, act-3. If `lint` reports a hit, reword the act (not the pattern). Fix the example, not the checker, unless the example exposes a real checker bug.

- [ ] **Step 7: Run the tests, look at the PDF, commit**

Run: `python3 -m unittest discover -s plugins/wrist/tests -q 2>&1 | tail -5` (expect `OK`). Then build the example in the scratchpad and look at its pages exactly as in Task 3 step 6 (use `publish wrist` on a scratch copy of the example and render page 1, the first script page, the page with "ACT TWO" and the last page). Confirm the title page lines, the act headings starting new pages, the indents and the page numbers.

```bash
git add -A plugins/wrist
git commit -m "feat(wrist): add the-third-bell example screenplay and its tests" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Skill, references and screenplay templates

**Files:**
- Modify: `plugins/wrist/skills/wrist/SKILL.md`, `references/grammar.md`, `references/publishing.md`
- Create: `plugins/wrist/skills/wrist/references/fountain.md`
- Create: `plugins/wrist/skills/wrist/assets/templates/screenplay/` with `PREMISE.md`, `synopsis.wrist.md`, `outline.wrist.md`, `characters.wrist.md`, `misc.wrist.md`, `act.wrist.md`
- Modify: `README.md` (the wrist section), `plugins/wrist/.claude-plugin/plugin.json` (description), `plugins/wrist/tests/test_docs.py`

**Interfaces:**
- Consumes: question ids and keys from Task 4; commands and messages from the earlier tasks.
- Produces: a `SKILL.md` that names three profiles, says how to write Fountain scenes, names the `Established:` loop for acts and the title-page questions, and points at `assets/templates/screenplay/` and `references/fountain.md`.

- [ ] **Step 1: Write the failing docs tests**

Add to `SkillText` in `plugins/wrist/tests/test_docs.py`:

```python
    def test_skill_covers_the_screenplay(self):
        skill = text(SKILL, "SKILL.md")
        for phrase in ("`screenplay`", "Fountain", "acts:", "assets/templates/screenplay/", "references/fountain.md",
                       "act_headings", "based_on", "realize the act, fill in `Established:`, stamp it"):
            self.assertIn(phrase, skill, phrase)

    def test_every_screenplay_template_exists(self):
        for name in ("PREMISE.md", "synopsis.wrist.md", "outline.wrist.md", "characters.wrist.md", "misc.wrist.md",
                     "act.wrist.md"):
            self.assertTrue(os.path.isfile(os.path.join(SKILL, "assets", "templates", "screenplay", name)), name)

    def test_the_fountain_reference_names_the_dialect(self):
        ref = text(SKILL, "references", "fountain.md")
        for phrase in ("INT.", "forced", "@@ACT", "dropped", "[[", "/*", "===", "TO:", "dual dialogue"):
            self.assertIn(phrase, ref, phrase)

    def test_the_grammar_reference_explains_publish_style_and_lint_format(self):
        grammar = text(SKILL, "references", "grammar.md")
        for phrase in ("publish", "style", "lint_format", "fountain", "action", "dialogue"):
            self.assertIn(phrase, grammar, phrase)

    def test_the_readme_lists_the_screenplay(self):
        self.assertIn("`shortstory`, `novel` and `screenplay`", text(ROOT, "README.md"))
```

Run: `python3 -m unittest discover -s plugins/wrist/tests -p test_docs.py 2>&1 | grep -E "^(FAIL|ERROR):|^Ran|^FAILED|^OK"` — expect failures.

- [ ] **Step 2: Write the six screenplay templates**

Create under `plugins/wrist/skills/wrist/assets/templates/screenplay/`:

`PREMISE.md`:

```markdown
---
profile: screenplay
title: <Title>
slug: <lower-case-words-joined-by-hyphens>
author: <Author name>
language: en
acts: <whole number, 1 to 7>
act_headings: <yes or no>
based_on: <optional: a line for the title page>
draft: <optional: draft name or date for the title page>
contact: <optional: a contact line for the title page>
---

# Premise

<One or two sentences: what this film is.>

## Answers

- **genre:** <answer>
- **premise:** <answer>
- **ending:** <answer>
- **tone:** <answer>
- **story:** <answer>
- **audience:** <answer>
- **format:** <answer>
- **runtime:** <answer>
- **themes:** <answer, or none (skipped on purpose)>
- **comps:** <answer>
- **setting:** <answer>
- **locations:** <answer>
- **characters:** <answer>
- **events:** <answer>
- **fixed:** <answer>
- **structure:** <answer, or an *UNKNOWN*: with Proposed:>
- **avoid:** <answer>
```

`synopsis.wrist.md`:

```markdown
# synopsis: <Title>

<What the synopsis must do.>

- **Logline:** <one sentence: who, what they want, what stands in the way>
- **Ending:** <how it ends>
- **Theme:** <what it is about underneath>
- **Rules:** <length, tense; must state the ending>
- **Required:** always
- **Depends on:** none
- **Unknowns:** none
```

`outline.wrist.md`:

```markdown
# outline: <Title>

<What the outline must do.>

- **Structure:** <chosen structure from structures.md, or *UNKNOWN*: with Proposed:>
- **Rules:** <how many beats, which pages each covers, what each must change>
- **Required:** always
- **Depends on:** [synopsis](./synopsis.md.wrist.md) (mentions)
- **Unknowns:** none

## beat: <Beat name>

- **Purpose:** <what this beat is for>
- **Change:** <what is different after it>
- **Pages:** <target page range, for example 1-10>
```

`characters.wrist.md`:

```markdown
# characters: <Title>

<What the registry must hold.>

- **Rules:** <which characters are named; naming rules>
- **Required:** always
- **Depends on:** [synopsis](./synopsis.md.wrist.md) (mentions)
- **Unknowns:** none

## character: <Name>

<Two lines of who they are.>

- **Wants:** <what they want in this film>
- **Flaw:** <what stands in their way>
- **Voice:** <how they speak>
- **Arc:** <where they start and where they end>
```

`misc.wrist.md`:

```markdown
# misc: <Title>

<What this file holds: locations, props, concepts and the timeline.>

- **Rules:** <what may and may not be named>
- **Required:** always
- **Depends on:** [synopsis](./synopsis.md.wrist.md) (mentions)
- **Unknowns:** none

## location: <Name>

- **Slug:** <the exact location name as written in scene headings, for example KITCHEN>
- **Facts:** <fixed facts the text must respect>

## prop: <Name>

- **Facts:** <fixed facts the text must respect>
```

`act.wrist.md` (copy once per act, named `act-<n>.md.wrist.md`, with `<n>` zero-padded to the width of the act count):

```markdown
# act: <Act name>

<What this act must do. Leave `Established:` empty until the act is realized; then list every new fact, date, injury, prop and promise the text fixed.>

- **Pages:** <target page range, for example 1-28>
- **Established:**
- **Required:** always
- **Rules:** <voice, forbidden moves, quality rules copied from quality.md>
- **Depends on:** [<Previous act>](./act-<n-1>.md.wrist.md) (continues)
- **Unknowns:** none

## scene: <Scene name>

- **Purpose:** <what the scene must do>
- **Location:** <a location Slug>
- **Pages:** <target page range>
- **Must include:** <images, lines or props that must appear>
- **Must avoid:** <what must not appear>
- **Depends on:** [<Beat name>](../outline.md.wrist.md#beat-<beat-slug>) (realizes)
- **Depends on:** [<Character>](../character.md.wrist.md#character-<character-slug>) (appears)
- **Depends on:** [<Location>](../misc.md.wrist.md#location-<location-slug>) (appears)
```

- [ ] **Step 3: Write `references/fountain.md`**

Create `plugins/wrist/skills/wrist/references/fountain.md`:

```markdown
# Fountain in wrist

The act files of a screenplay are written in Fountain, the plain-text screenplay format. wrist reads Fountain 1.1 with its own pandoc reader (`publish/screenplay/fountain.lua`). Write the way a screenwriter would; the reader decides what each line is.

## Elements

- **Scene heading:** a line starting `INT.`, `EXT.`, `EST.`, `INT./EXT.`, `INT/EXT` or `I/E` (any case), with a blank line before and after: `INT. FERRY DECK - NIGHT`. Force one that does not start that way with a leading `.`: `.THE BEACH`. A `..` start is not forced.
- **Action:** every other paragraph. One action beat per paragraph, four lines or fewer, present tense, only what the camera can see. A leading `!` forces action: `!MARIT`.
- **Character:** an upper-case line (letters, digits, and an optional extension in brackets such as `(V.O.)`, `(O.S.)`, `(CONT'D)`) with a blank line before it and dialogue right after it, no blank line between. Force a mixed-case name with a leading `@`: `@McCLOUD`. An upper-case line with no dialogue after it is action.
- **Dialogue:** the lines after a character cue, up to the blank line.
- **Parenthetical:** a line wrapped in brackets inside dialogue: `(quietly)`. Use sparingly.
- **Transition:** an upper-case line ending `TO:` with a blank line before and after (`CUT TO:`), or forced with a leading `>`: `> Burn to white.`
- **Centered:** `> THE END <`.
- **Page break:** a line of three or more `=`.
- **Emphasis:** `*italic*`, `**bold**` and `_underline_` (underline is typeset as italic).

## Dropped

Notes `[[like this]]`, boneyard `/* like this */` (either may span lines), sections (lines starting `#`), synopses (lines starting a single `=`) and a Fountain title page are removed. The title page is built from `PREMISE.md` instead.

## wrist's own line

`@@ACT ONE@@` on a line of its own is a marker the publisher writes into `output/` before each act when `act_headings: yes`. Never write it into an act file; Fountain applications treat it as action.

## Not supported

Dual dialogue (`^` after a character) is read as ordinary sequential dialogue. Scene numbers (`#12#` at the end of a heading) are dropped. Revision marks and locked pages are not supported.
```

- [ ] **Step 4: Edit `SKILL.md`, the references, the README and the manifest**

Apply these replacements to `plugins/wrist/skills/wrist/SKILL.md` (assert each anchor; read the file first and adjust whitespace rather than skipping an edit):

1. Replace the sentence beginning `Two profiles exist: `shortstory` and `novel`.` through the end of that paragraph with: `Three profiles exist: `shortstory`, `novel` and `screenplay`. If the user wants a poem, say it is not built yet. Each profile has its own folder under `profiles/` (questions, structures, quality lists) and its own templates: `assets/templates/` for the short story, `assets/templates/novel/` for the novel and `assets/templates/screenplay/` for the screenplay. A screenplay's acts are written in Fountain; read `references/fountain.md` before writing one.`
2. In Premise step 1, change `(`shortstory` or `novel`)` to `(`shortstory`, `novel` or `screenplay`)`.
3. At the end of Premise step 3, add: `For a screenplay the front matter holds `acts:` (a whole number from 1 to 7; if the user is unsure, propose one from the runtime and the structure, then fix it) and `act_headings:` (`yes` or `no`: a feature has none, a TV-style or stage script does). A page is about a minute, so ask for the runtime and keep the page targets in the outline honest.`
4. In Generation step 3, after the novel sentence, add: `For a screenplay write one act stand-in per act, named with the number zero-padded to the width of the act count, with a `(continues)` link to the act before and `Established:` left empty. Give every location a `Slug:` and use it exactly in the scene headings.`
5. In Realization step 2, after the novel sentence, add: `For a screenplay, write each act as Fountain (see `references/fountain.md`): a scene heading for every scene, one action beat per paragraph of four lines or fewer, only what the camera can see, no camera directions in a spec script, dialogue with subtext. Work one act at a time: realize the act, fill in `Established:`, stamp it, then go on. `stamp` refuses an act whose `Established:` is empty.`
6. In Publishing step 1, add: `For a screenplay also ask for the title page lines (each optional, one line): `based_on:` (for example "Based on a short story by ..."), `draft:` (a draft name or date) and `contact:`; and the paper (`trim:` `a4` for A4; US letter by default).`
7. Ensure the verbatim phrases the docs test looks for are present, including `realize the act, fill in `Established:`, stamp it`.

Append to `references/grammar.md`:

```markdown
- **`publish`**: an object with a `style` name that picks how the work is published: `story`, `book` or `screenplay`. Without it the style is inferred: `book` when the profile has a `sequence` function, otherwise `story`. A profile with `style: screenplay` is written in Fountain (see `fountain.md`) and published in screenplay layout.
- **`lint_format`**: `prose` (the default) or `fountain`. It decides which scopes a lint pattern may use: `narration` or `anywhere` for prose; `action` (action lines only), `dialogue` (dialogue and parentheticals) or `anywhere` for Fountain.
```

Append to `references/publishing.md`, before `## When the build fails`:

```markdown
## A screenplay

A screenplay is read with the Fountain reader and laid out as a script: US letter (A4 with `trim: a4`), a 12 pt monospace font taken from the list Courier Prime, Courier New, DejaVu Sans Mono (the last is bundled with typst), margins 1.5 inches left and 1 inch elsewhere, about 55 lines and about a minute a page. The title page has the title, "Written by", the author, and the optional `based_on`, `draft` and `contact` lines; it carries no number and neither does the first script page; later pages show "2." and so on at the top right. With `act_headings: yes` each act starts a new page with a centered "ACT ONE"-style heading. The EPUB is a monospace reading copy of the same elements. No copyright page, dedication, epigraph or contents page is built.
```

In `README.md`, change the wrist section sentence that names the profiles to read "`shortstory`, `novel` and `screenplay` exist; the poem profile is planned." (read the section and edit the wrapped lines in place). In `plugin.json` change `Profiles: short story and novel` to `Profiles: short story, novel and screenplay`.

- [ ] **Step 5: Run the tests and commit**

Run: `python3 -m unittest discover -s plugins/wrist/tests -q 2>&1 | tail -4` — expect `OK`.

```bash
git add -A plugins/wrist README.md
git commit -m "docs(wrist): teach the skill and references the screenplay profile" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Trial: a fresh session writes a tiny screenplay

This task is performed by the executor, not by a test. Each earlier trial found defects the test suites could not, so it is required for the cycle to be called done.

**Files:**
- Create: `notes/wrist-screenplay-trial.md` (untracked notes)
- Modify: whatever the trial exposes, with a failing test first for each code defect

- [ ] **Step 1: Set up the harness**

Reuse the novel trial's helper, pointed at a new scratch directory:

```bash
S=/tmp/claude-1000/-home-sean-Data-Projects-claude-plugins/b823c3ae-57a6-454b-b3b3-63ef3fa1a7f8/scratchpad
rm -rf $S/strial && mkdir -p $S/strial && cd $S/strial && git init -q .
sed 's#/ntrial#/strial#; s#nturn-#sturn-#g' $S/nturn.sh > $S/sturn.sh && chmod +x $S/sturn.sh
grep -n "strial\|sturn" $S/sturn.sh | head -4
```

- [ ] **Step 2: Run the conversation**

Four to six resumed turns, playing the author, with a premise unlike the example: a tiny two-act short film of about four pages ("a retired cartographer redraws a map she knows is wrong"), genre quiet drama with a touch of humour, `act_headings: no`, title page lines wanted (`draft`, `contact`), runtime four minutes, a deliberate gap (skip comps and themes). Turn 1: "I'd like to write a screenplay." Then answer its questions, accept its proposals, and ask it to continue through generation, realization (one act at a time) and publishing. Record each turn's cost and result.

- [ ] **Step 3: Inspect the output yourself**

Read every stand-in and the Fountain acts. Run `check`, `status`, `lint` and the three gates with the plugin's scripts. Render the PDF pages (the scratch virtualenv) and look at the title page, the indents, the page numbers and the page count against the runtime; open the EPUB structure. Compare the script with the stand-ins as the author: did it write real Fountain, keep slug lines consistent with the declared locations, fill `Established:` honestly, record its own choices as unknowns, add facts the stand-ins do not hold?

- [ ] **Step 4: Fix and record**

For each defect: a failing test first for a code defect, the smallest fix, the suite green, a commit. Guidance defects go into `SKILL.md` with a test pinning the phrase. Write the findings in `notes/wrist-screenplay-trial.md`, each marked `[observed]` or `[not verified]`, and say what was fixed and what was left. Do not report anything as a mistake before you have checked it against the stand-ins and the premise.

- [ ] **Step 5: Commit**

```bash
git add -A plugins/wrist
git commit -m "fix(wrist): close the defects the screenplay trial exposed" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

(Skip if the trial exposed nothing to fix, and say so.)

---

### Task 8: Whole-plugin verification

- [ ] **Step 1: Full suites**

Run: `python3 -m unittest discover -s plugins/wrist/tests -q 2>&1 | tail -4; python3 -m unittest discover -s plugins/skel/tests -q 2>&1 | tail -3`
Expected: wrist `OK` with no skips (pandoc and typst are installed); skel `OK` (223 tests), unchanged.

- [ ] **Step 2: All three examples as a user**

```bash
cd /home/sean/Data/Projects/claude-plugins/plugins/wrist/skills/wrist/assets/examples
S=../../../scripts/wrist_check.py
for e in the-lamp salt-road the-third-bell; do (cd $e && echo "-- $e" && python3 $S check wrist | tail -1 && python3 $S status wrist | head -1 && python3 $S lint wrist | grep hits && for p in generation realization publishing; do python3 $S gate wrist $p; done; ls); done
```

Expected: all `0 errors, 0 warnings`, every file realized, 0 lint hits, all nine gates open, no `output/` folder in any example.

- [ ] **Step 3: Leftover scan**

Run: `grep -rniE "skel|TODO|TBD|FIXME" plugins/wrist -I | grep -vi 'skelet' | grep -v 'tests/'`
Expected: only the informal-marker regex, the `todo` variable names in `wrist_check.py` and the grammar's description of informal markers.

- [ ] **Step 4: Bring the spec in line**

Edit the screenplay spec where the build departed from it, adding each departure as a numbered line under "Open decisions", and commit with the final fixes.

```bash
git add -A docs plugins/wrist
git commit -m "docs(wrist): bring the screenplay spec in line with the build" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

## Self-review

**1. Spec coverage**

| Spec section | Task |
|---|---|
| Decisions: Fountain via a Lua reader; industry title page; `act_headings` off by default | 2, 3, 4 |
| `publish.style`, registry, inference, unknown-style error | 1 (setting), 3 (registry) |
| `lint_format`, scopes, `classify_fountain` | 1 |
| Shared Fountain cases against both implementations | 1, 2 |
| The reader's rules, forced forms, dropped forms, `@@ACT` marker | 2 |
| PDF layout, indents, numbering, title page, act headings | 3 |
| EPUB classes and stylesheet, no stray contents entry | 3 |
| Pipeline (`--from` reader, filter, template, marker files removed) | 3 |
| File shape, premise keys, functions and fields, relations, settings | 4 |
| Structures with page maps, format table, questions, quality data, lint patterns | 4 |
| Skill, references (`fountain.md`), templates, README | 6 |
| Example, engine, publish tests, trial | 5, 1 to 3, 7 |
| Out of scope (poem, slug/location check, page count, dual dialogue, TV/stage) | not built |
| Open decisions 1 to 9 | built as written; 2 and 3 verified visually |

Additions beyond the spec, all forced by building it: premise keys may contain underscores and a question id `act-headings` stands for the key `act_headings` (the existing hyphen-only key rule made `act_headings` unreadable from `PREMISE.md`), recorded in Task 4 step 1.

**2. Placeholder scan:** no step is left to improvise. The `<...>` markers in templates are intended slots. Task 5 step 1 and Task 4 step 5 each carry a parenthetical about replacing an escape with a real character or simplifying a loop line; do them while writing, not after.

**3. Type consistency:** `Profile.publish_style`, `Profile.lint_format`, `question_key(qid)` (Tasks 1 and 4); `wrist_lint.classify_fountain/elements/strip_comments/mask_comments/lint_text(text, items, lint_format)` (Task 1, used by Tasks 2 and 5 tests and `cmd_lint`); `wrist_publish.style_for/with_act_markers/remove_markers/plan_screenplay/NUMBER_WORDS/SCREENPLAY_KEYS/STYLES` (Task 3, used by `cmd_publish` and tests). The reader's class names (`scene-heading`, `action`, `character`, `dialogue`, `parenthetical`, `transition`, `centered`, `act-marker`, `pagebreak`) match across `fountain.lua`, `screenplay.lua`, `screenplay.css`, `screenplay.typ` function names (`sp-heading`, ...) and the tests. Question ids and premise keys match between `profile.json`, `questions.md`, the example's `PREMISE.md` and the tests.

**4. Review Focus coverage:** items 1 and 5 are in Task 1 (`SharedCases`, `FountainLint`, `LuaReader`); item 2 is `ThirdBellFileSet`; items 3, 4 and 6 are in `RealBuilds`, `ScreenplayPlan` and `TemplateText`, with the rendered-page check in Task 3 step 6.

**Known risks the executor should watch:**
- Task 1 edits `wrist_profile.py` and `wrist_check.py` by anchor strings; the scripts assert each exists, so read an assertion failure as a drifted anchor, not a reason to skip the edit.
- The layout (indents, page numbers, act headings) is verified only by looking at rendered pages; Task 3 step 6 and Task 5 step 7 are not optional.
- Fountain's rules are subtle; when the Lua reader and the Python classifier disagree on a case, decide by the Fountain specification, fix both and the case file together, and ledger it.
- The trial costs money and time; keep the screenplay tiny.
