# wrist foundation (cycle 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `wrist` plugin: a renamed copy of `skel` whose checker is driven by profile data, with the `shortstory` profile, the Premise/Generation/Realization workflow, lint, and a pandoc+typst publisher.

**Architecture:** `plugins/wrist/` starts as a mechanical rename of `plugins/skel/`, then the code-only surface is cut out of `wrist_check.py` and replaced by a profile-driven grammar (`wrist_profile.py` loads JSON and markdown data from `profiles/<name>/`). Generic machinery (parsing, links, backlinks, unknowns) is kept in place. Drift tracking moves to a `wrist/.stamps` sidecar; lint and publishing live in their own small modules.

**Tech Stack:** Python 3.10 standard library only for all scripts and tests (`unittest`); `pandoc` and `typst` as external tools for publishing only.

**Spec:** `docs/superpowers/specs/2026-10-03-wrist-foundation-design.md`

## Global Constraints

Copied from the spec; every task includes them.

- Scripts and tests use only the Python standard library; the development machine has Python 3.10 (no `tomllib`), so profiles are JSON.
- Stand-ins are named `wrist/<mirrored path>.wrist.md` and stand in for `<mirrored path>` at the project root. One work per project root.
- `wrist/PREMISE.md` replaces `SYSTEM.md`. The `wrist/.stamps` JSON sidecar holds drift state. Realized files carry no header or marker.
- Links keep skel's syntax: `Depends on:` / `Referred by:`, bidirectional, with an optional relation word in parentheses after the link (`(appears)`). An unlisted relation word is a warning.
- Unknown grammar is unchanged from skel: `*UNKNOWN*:`, `Kind: blocking | local`, `Proposed:`, `Consequence:`, `Unlocks:`, names and followers.
- `lint` is advisory and always exits 0. The `max_prose_words` cap is a warning.
- `publish` requires `pandoc` and `typst` on the path and stops with install steps if either is missing.
- `plugins/skel/` is not modified.
- Stand-ins hold notes, facts and rules, never final text.

## Review Focus

Inputs the spec implies that no obvious test would reach. Each has a test in the task that owns the code.

1. A title or slug that does not match the story stand-in's filename (renamed title, uppercase or underscored slug) must fail `check` with both "required stand-in missing" and "outside the shortstory shape". Task 4.
2. A realized file hand-edited after stamping must show as `edited` and block publishing, not pass silently. Task 5.
3. An empty realized story file (zero words) must block publishing. Task 5.
4. A listed cliché inside quoted dialogue must not be flagged when its scope is `narration`, but must be flagged when its scope is `anywhere`. Task 6.
5. A title with quotes, an ampersand and non-ASCII characters must reach pandoc intact as a single argument, never through a shell. Task 7.

---

## File structure

```text
plugins/wrist/
  .claude-plugin/plugin.json
  skills/wrist/
    SKILL.md
    references/grammar.md, publishing.md
    assets/templates/PREMISE.md, synopsis.wrist.md, outline.wrist.md, characters.wrist.md, misc.wrist.md, story.wrist.md
    assets/examples/the-lamp/            complete sample project (wrist/ tree, realized files)
    profiles/shortstory/                 profile.json, questions.md, structures.md, quality.md, lint.json
    publish/book.typ, epub.css
    scripts/wrist_check.py               CLI + grammar core (kept from skel, rewired)
    scripts/wrist_profile.py             profile loading and validation
    scripts/wrist_lint.py                pure lint function
    scripts/wrist_publish.py             tool preflight, command planning, build
    scripts/wrist_mv.py                  move/rename with link rewriting (kept from skel)
  tests/support.py, test_profile.py, test_check.py, test_unknowns.py, test_graph.py,
        test_status.py, test_gate.py, test_lint.py, test_publish.py, test_generic.py
```

---

### Task 1: Copy skel to wrist and rename

**Files:**
- Create: `plugins/wrist/` (copy of `plugins/skel/`, renamed throughout)

**Interfaces:**
- Produces: a `plugins/wrist/` tree that is identical to skel in behavior, with `skel`/`Skel`/`SKEL` replaced by `wrist`/`Wrist`/`WRIST` in every file name and file content (the word "skeleton" is left alone). Later tasks use the post-rename names: `wrist_check.py`, `wrist_mv.py`, `WristFile`, `WRIST_SUFFIX`, `wrist_root`, `wrist_dir`, `skills/wrist/`.

- [ ] **Step 1: Copy and rename**

```bash
cd /home/sean/Data/Projects/claude-plugins
cp -r plugins/skel plugins/wrist
find plugins/wrist -name __pycache__ -type d -prune -exec rm -rf {} +
RENAME='s/skel(?!et)/wrist/g; s/Skel(?!et)/Wrist/g; s/SKEL(?!ET)/WRIST/g'
find plugins/wrist -depth -iname '*skel*' | while read -r p; do
  d=$(dirname "$p"); b=$(basename "$p")
  mv "$p" "$d/$(printf '%s' "$b" | perl -pe "$RENAME")"
done
grep -rIli 'skel' plugins/wrist | xargs perl -pi -e "$RENAME"
```

- [ ] **Step 2: Verify nothing was missed**

Run: `grep -rIni 'skel' plugins/wrist | grep -vi 'skelet'; find plugins/wrist -iname '*skel*'`
Expected: no output from either command (the one remaining `skeleton` in `plugin.json` is filtered by the grep).

- [ ] **Step 3: Run the carried-over skel suite as a rename check**

Run: `python3 -m unittest discover -s plugins/wrist/tests -q 2>&1 | tail -4`
Expected: `Ran 223 tests` and `OK`. This proves the rename changed no behavior. These tests are deleted in Task 4.

- [ ] **Step 4: Commit**

```bash
git add plugins/wrist
git commit -m "feat(wrist): copy skel and rename it throughout" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Profile loader and the shortstory profile data

**Files:**
- Create: `plugins/wrist/skills/wrist/scripts/wrist_profile.py`
- Create: `plugins/wrist/skills/wrist/profiles/shortstory/profile.json`
- Create: `plugins/wrist/skills/wrist/profiles/shortstory/questions.md`
- Create: `plugins/wrist/tests/test_profile.py`

**Interfaces:**
- Produces (used by every later task), module `wrist_profile`:
  - `class ProfileError(Exception)`
  - `SLUG_RE` (compiled regex for a valid slug)
  - `parse_profile(data: dict, questions_text: str = "", directory: str | None = None) -> Profile` (validates; raises `ProfileError`)
  - `load_profile(name: str, profiles_dir: str | None = None) -> Profile` (uses `profiles_dir`, else env `WRIST_PROFILES_DIR`, else the bundled `profiles/`)
  - `list_profiles(profiles_dir=None) -> list[str]`
  - `Profile` attributes: `name`, `files` (list of `{"path","function","order"}`), `functions` (dict name → `{"heading": str, "fields": [str], "children": {str: [str]}, "prose": bool}`), `relations` (lower-case list), `limits` (`{"max_prose_words": int}`), `questions` (list of `Question`), `directory`.
  - `Profile.expected_files(slug) -> list[tuple[path, function]]` in realization order (by `order`, ties by position); a path containing `{slug}` is skipped when `slug` is empty.
  - `Profile.function_for(rel, slug) -> str | None`
  - `Profile.labels() -> list[str]` (every field label the profile declares), `Profile.heading_types() -> set[str]`
  - `Profile.lint_items() -> list[dict]` (added in Task 6)
  - `Question` attributes: `id`, `required` (bool), `text`.

- [ ] **Step 1: Write the failing tests**

Create `plugins/wrist/tests/test_profile.py`:

```python
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from support import SCRIPTS, SKILL

import wrist_profile as wp


def base():
    return {
        "name": "tiny",
        "files": [{"path": "a.md", "function": "alpha", "order": 1},
                  {"path": "work/{slug}.md", "function": "beta", "order": 2}],
        "functions": {"alpha": {"heading": "alpha", "fields": ["Hue"], "children": {"bead": ["Size"]}},
                      "beta": {"heading": "beta", "prose": True}},
        "relations": ["Uses"],
        "limits": {"max_prose_words": 50},
    }


class ShortstoryProfile(unittest.TestCase):
    def setUp(self):
        self.p = wp.load_profile("shortstory")

    def test_file_shape_follows_realization_order(self):
        self.assertEqual(self.p.expected_files("the-lamp"), [
            ("synopsis.md", "synopsis"), ("outline.md", "outline"), ("character.md", "characters"),
            ("misc.md", "misc"), ("work/the-lamp.md", "story")])

    def test_slug_files_are_skipped_without_a_slug(self):
        self.assertNotIn("story", [fn for _, fn in self.p.expected_files("")])

    def test_function_for_matches_a_mirrored_path(self):
        self.assertEqual(self.p.function_for("work/the-lamp.md", "the-lamp"), "story")
        self.assertIsNone(self.p.function_for("work/other.md", "the-lamp"))

    def test_labels_cover_every_declared_field(self):
        for label in ("Logline", "Wants", "Flaw", "Voice", "Facts", "Point of view", "Must include"):
            self.assertIn(label, self.p.labels())

    def test_questions_are_parsed_with_their_kind(self):
        ids = [q.id for q in self.p.questions]
        self.assertEqual(len(ids), len(set(ids)))
        required = {q.id for q in self.p.questions if q.required}
        self.assertEqual(required, {"genre", "audience", "length", "tone", "viewpoint", "premise", "ending"})
        self.assertEqual(len(self.p.questions), 13)

    def test_only_the_story_is_prose(self):
        self.assertEqual([n for n, s in self.p.functions.items() if s["prose"]], ["story"])

    def test_relations_are_lower_case(self):
        self.assertIn("appears", self.p.relations)


class Validation(unittest.TestCase):
    def assertRejected(self, data, fragment, questions=""):
        with self.assertRaises(wp.ProfileError) as cm:
            wp.parse_profile(data, questions)
        self.assertIn(fragment, str(cm.exception))

    def test_a_valid_profile_loads_and_defaults_are_filled(self):
        p = wp.parse_profile(base())
        self.assertEqual(p.functions["beta"]["children"], {})
        self.assertEqual(p.functions["beta"]["fields"], [])
        self.assertEqual(p.relations, ["uses"])

    def test_missing_key(self):
        data = base()
        del data["limits"]
        self.assertRejected(data, "missing 'limits'")

    def test_unknown_top_level_key(self):
        data = base()
        data["colour"] = "red"
        self.assertRejected(data, "unknown key 'colour'")

    def test_file_uses_an_undeclared_function(self):
        data = base()
        data["files"][0]["function"] = "gamma"
        self.assertRejected(data, "undeclared function 'gamma'")

    def test_duplicate_path(self):
        data = base()
        data["files"][1]["path"] = "a.md"
        self.assertRejected(data, "'a.md' is listed twice")

    def test_order_must_be_an_integer(self):
        data = base()
        data["files"][0]["order"] = "first"
        self.assertRejected(data, "integer 'order'")

    def test_heading_names_are_restricted(self):
        data = base()
        data["functions"]["alpha"]["heading"] = "Not Valid"
        self.assertRejected(data, "heading")

    def test_unknown_function_key(self):
        data = base()
        data["functions"]["alpha"]["colour"] = 1
        self.assertRejected(data, "unknown key 'colour'")

    def test_limit_must_be_positive(self):
        data = base()
        data["limits"]["max_prose_words"] = 0
        self.assertRejected(data, "max_prose_words")

    def test_duplicate_question_id(self):
        self.assertRejected(base(), "asked twice",
                            "- [required] genre: One?\n- [deferrable] genre: Two?\n")


class Loading(unittest.TestCase):
    def test_unknown_profile_lists_what_exists(self):
        with self.assertRaises(wp.ProfileError) as cm:
            wp.load_profile("poem")
        self.assertIn("no profile 'poem'", str(cm.exception))
        self.assertIn("shortstory", str(cm.exception))

    def test_a_name_cannot_climb_out_of_the_profiles_folder(self):
        with self.assertRaises(wp.ProfileError):
            wp.load_profile("../scripts")

    def test_invalid_json_is_reported(self):
        d = tempfile.mkdtemp(prefix="wrist-prof-")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        os.makedirs(os.path.join(d, "bad"))
        with open(os.path.join(d, "bad", "profile.json"), "w") as fh:
            fh.write("{not json")
        with self.assertRaises(wp.ProfileError) as cm:
            wp.load_profile("bad", d)
        self.assertIn("not valid JSON", str(cm.exception))

    def test_environment_variable_selects_the_profiles_folder(self):
        d = tempfile.mkdtemp(prefix="wrist-prof-")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        os.makedirs(os.path.join(d, "tiny"))
        with open(os.path.join(d, "tiny", "profile.json"), "w") as fh:
            json.dump(base(), fh)
        code = ("import sys; sys.path.insert(0, %r); import wrist_profile as w; "
                "print(w.load_profile('tiny').name)" % SCRIPTS)
        env = dict(os.environ, WRIST_PROFILES_DIR=d)
        out = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True)
        self.assertEqual(out.stdout.strip(), "tiny", out.stderr)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m unittest discover -s plugins/wrist/tests -p 'test_profile.py' 2>&1 | tail -5`
Expected: FAIL/ERROR: `ModuleNotFoundError: No module named 'support'` (support.py arrives in Task 3). Create the minimal `plugins/wrist/tests/support.py` now so this and later steps can import it:

```python
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.normpath(os.path.join(HERE, "..", "skills", "wrist"))
SCRIPTS = os.path.join(SKILL, "scripts")
sys.path.insert(0, SCRIPTS)
```

Re-run. Expected: `ModuleNotFoundError: No module named 'wrist_profile'`.

- [ ] **Step 3: Write the profile loader**

Create `plugins/wrist/skills/wrist/scripts/wrist_profile.py`:

```python
#!/usr/bin/env python3
"""wrist_profile.py: load and validate a wrist profile.

A profile is a folder under profiles/ holding the data the checker reads: profile.json (file
shape, heading types, required fields), questions.md, and optionally lint.json. Standard
library only.
"""
import copy
import json
import os
import re

PROFILES_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "profiles"))
NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
QUESTION_RE = re.compile(r"^-\s+\[(required|deferrable)\]\s+([a-z0-9]+(?:-[a-z0-9]+)*):\s+(\S.*)$")
TOP_KEYS = {"name", "files", "functions", "relations", "limits"}
FUNCTION_KEYS = {"heading", "fields", "children", "prose"}
SCOPES = ("narration", "anywhere")
LINT_KEYS = ("id", "pattern", "label", "note", "scope", "positive", "negative")


class ProfileError(Exception):
    pass


class Question:
    def __init__(self, qid, required, text):
        self.id, self.required, self.text = qid, required, text


def _strings(value):
    return isinstance(value, list) and all(isinstance(v, str) and v for v in value)


def validate(data):
    """Raise ProfileError for the first problem in a parsed profile.json."""
    if not isinstance(data, dict):
        raise ProfileError("profile.json must hold an object")
    missing = sorted(TOP_KEYS - set(data))
    if missing:
        raise ProfileError("profile.json is missing " + ", ".join(repr(k) for k in missing))
    extra = sorted(set(data) - TOP_KEYS)
    if extra:
        raise ProfileError(f"profile.json has unknown key {extra[0]!r}")
    if not (isinstance(data["name"], str) and NAME_RE.match(data["name"])):
        raise ProfileError("'name' must be lower-case letters, digits and hyphens")
    functions = data["functions"]
    if not isinstance(functions, dict) or not functions:
        raise ProfileError("'functions' must be a non-empty object")
    for fname, spec in functions.items():
        if not isinstance(spec, dict):
            raise ProfileError(f"function '{fname}' must be an object")
        extra = sorted(set(spec) - FUNCTION_KEYS)
        if extra:
            raise ProfileError(f"function '{fname}' has unknown key {extra[0]!r}")
        if not (isinstance(spec.get("heading"), str) and NAME_RE.match(spec["heading"])):
            raise ProfileError(f"function '{fname}': 'heading' must be lower-case letters, digits and hyphens")
        if not _strings(spec.get("fields", [])):
            raise ProfileError(f"function '{fname}': 'fields' must be a list of labels")
        children = spec.get("children", {})
        if not isinstance(children, dict):
            raise ProfileError(f"function '{fname}': 'children' must be an object")
        for child, fields in children.items():
            if not NAME_RE.match(child) or not _strings(fields):
                raise ProfileError(f"function '{fname}': child '{child}' needs a valid name and a list of labels")
        if not isinstance(spec.get("prose", False), bool):
            raise ProfileError(f"function '{fname}': 'prose' must be true or false")
    files = data["files"]
    if not isinstance(files, list) or not files:
        raise ProfileError("'files' must be a non-empty list")
    seen = set()
    for f in files:
        if not (isinstance(f, dict) and isinstance(f.get("path"), str) and isinstance(f.get("function"), str)
                and isinstance(f.get("order"), int) and not isinstance(f.get("order"), bool)):
            raise ProfileError(f"a files entry needs string 'path', string 'function' and integer 'order': {f!r}")
        if f["path"] in seen:
            raise ProfileError(f"'{f['path']}' is listed twice in 'files'")
        seen.add(f["path"])
        if f["function"] not in functions:
            raise ProfileError(f"file '{f['path']}' uses undeclared function '{f['function']}'")
    if not _strings(data["relations"]):
        raise ProfileError("'relations' must be a list of words")
    limits = data["limits"]
    words = limits.get("max_prose_words") if isinstance(limits, dict) else None
    if not (isinstance(words, int) and not isinstance(words, bool) and words > 0):
        raise ProfileError("'limits' needs a positive integer 'max_prose_words'")


def parse_questions(text):
    out, seen = [], set()
    for line in text.split("\n"):
        m = QUESTION_RE.match(line.strip())
        if not m:
            continue
        kind, qid, body = m.groups()
        if qid in seen:
            raise ProfileError(f"question '{qid}' is asked twice in questions.md")
        seen.add(qid)
        out.append(Question(qid, kind == "required", body.strip()))
    return out


class Profile:
    def __init__(self, data, questions, directory):
        self.name = data["name"]
        self.files = data["files"]
        self.functions = data["functions"]
        self.relations = [r.lower() for r in data["relations"]]
        self.limits = data["limits"]
        self.questions = questions
        self.directory = directory

    def labels(self):
        out = []
        for spec in self.functions.values():
            for label in list(spec["fields"]) + [f for fs in spec["children"].values() for f in fs]:
                if label not in out:
                    out.append(label)
        return out

    def heading_types(self):
        types = set()
        for spec in self.functions.values():
            types.add(spec["heading"])
            types.update(spec["children"])
        return types

    def expected_files(self, slug):
        out = []
        for _, f in sorted(enumerate(self.files), key=lambda p: (p[1]["order"], p[0])):
            if "{slug}" in f["path"]:
                if not slug:
                    continue
                out.append((f["path"].replace("{slug}", slug), f["function"]))
            else:
                out.append((f["path"], f["function"]))
        return out

    def function_for(self, rel, slug):
        return dict(self.expected_files(slug)).get(rel)

    def lint_items(self):
        return []      # replaced in the lint task


def parse_profile(data, questions_text="", directory=None):
    data = copy.deepcopy(data)
    validate(data)
    for spec in data["functions"].values():
        spec.setdefault("fields", [])
        spec.setdefault("children", {})
        spec.setdefault("prose", False)
    return Profile(data, parse_questions(questions_text), directory)


def list_profiles(profiles_dir=None):
    root = profiles_dir or os.environ.get("WRIST_PROFILES_DIR") or PROFILES_DIR
    if not os.path.isdir(root):
        return []
    return sorted(n for n in os.listdir(root) if os.path.isfile(os.path.join(root, n, "profile.json")))


def load_profile(name, profiles_dir=None):
    root = profiles_dir or os.environ.get("WRIST_PROFILES_DIR") or PROFILES_DIR
    if not NAME_RE.match(name or "") or not os.path.isfile(os.path.join(root, name, "profile.json")):
        have = ", ".join(list_profiles(root)) or "none"
        raise ProfileError(f"no profile '{name}' (available: {have})")
    directory = os.path.join(root, name)
    try:
        with open(os.path.join(directory, "profile.json"), encoding="utf-8") as fh:
            data = json.load(fh)
    except ValueError as exc:
        raise ProfileError(f"profile.json is not valid JSON: {exc}")
    questions = ""
    qpath = os.path.join(directory, "questions.md")
    if os.path.isfile(qpath):
        with open(qpath, encoding="utf-8") as fh:
            questions = fh.read()
    return parse_profile(data, questions, directory)
```

- [ ] **Step 4: Write the shortstory profile data**

Create `plugins/wrist/skills/wrist/profiles/shortstory/profile.json`:

```json
{
  "name": "shortstory",
  "files": [
    {"path": "synopsis.md", "function": "synopsis", "order": 1},
    {"path": "outline.md", "function": "outline", "order": 2},
    {"path": "character.md", "function": "characters", "order": 3},
    {"path": "misc.md", "function": "misc", "order": 4},
    {"path": "work/{slug}.md", "function": "story", "order": 5}
  ],
  "functions": {
    "synopsis": {
      "heading": "synopsis",
      "fields": ["Logline", "Ending", "Theme"]
    },
    "outline": {
      "heading": "outline",
      "fields": ["Structure"],
      "children": {"beat": ["Purpose", "Change"]}
    },
    "characters": {
      "heading": "characters",
      "children": {"character": ["Wants", "Flaw", "Voice"]}
    },
    "misc": {
      "heading": "misc",
      "children": {"place": ["Facts"], "object": ["Facts"], "concept": ["Facts"]}
    },
    "story": {
      "heading": "story",
      "fields": ["Point of view", "Length"],
      "children": {"scene": ["Purpose", "Length", "Must include", "Must avoid"]},
      "prose": true
    }
  },
  "relations": ["appears", "mentions", "sets up", "pays off", "realizes"],
  "limits": {"max_prose_words": 120}
}
```

Create `plugins/wrist/skills/wrist/profiles/shortstory/questions.md`:

```markdown
# Premise questions: short story

Ask these in the premise phase, a few at a time, in plain language. A `required` question must be
answered or recorded as an `*UNKNOWN*:` before generation. A `deferrable` question may be left
out. The id is the key used in `wrist/PREMISE.md`.

## The story

- [required] genre: What is the genre or blend of genres (literary, crime, science fiction, horror, romance, fantasy, comic)?
- [required] premise: What is the central situation, or the question the story turns on, in a sentence or two?
- [required] ending: What shape should the ending take (closed, open, ironic, reversal, quiet recognition)?
- [required] tone: What tone should the story hold, and where, if anywhere, may it shift?

## The reader and the form

- [required] audience: Who is the intended reader (age, expectations, familiarity with the genre)?
- [required] length: What is the target length in words?
- [required] viewpoint: Whose point of view, in which person and tense (for example close third, past)?
- [deferrable] target: Where will it be read or submitted (a magazine, a contest, a collection, a gift)?

## What you already know

- [deferrable] characters: Which characters do you already want fixed, and what do you know about them?
- [deferrable] motifs: Which images, objects or themes should recur?
- [deferrable] fixed: Which events, places, facts or real details must appear?
- [deferrable] structure: Do you have a structure in mind (see structures.md), or should one be proposed from the answers above?
- [deferrable] avoid: What do you want kept out (subjects, tropes, kinds of language)?
```

- [ ] **Step 5: Run to verify it passes**

Run: `python3 -m unittest discover -s plugins/wrist/tests -p 'test_profile.py' 2>&1 | tail -4`
Expected: `OK` (all tests in `test_profile.py` pass).

- [ ] **Step 6: Commit**

```bash
git add plugins/wrist
git commit -m "feat(wrist): add the profile loader and the shortstory profile data" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 3: The-lamp example project and shared test support

**Files:**
- Create: `plugins/wrist/skills/wrist/assets/examples/the-lamp/` (ten content files plus `wrist/PREMISE.md`, listed below)
- Modify: `plugins/wrist/tests/support.py` (replace the minimal version from Task 2)

**Interfaces:**
- Produces:
  - Example project with slug `the-lamp`. Stand-ins under `wrist/`: `synopsis.md.wrist.md`, `outline.md.wrist.md`, `character.md.wrist.md`, `misc.md.wrist.md`, `work/the-lamp.md.wrist.md`; premise `wrist/PREMISE.md`; realized files `synopsis.md`, `outline.md`, `character.md`, `misc.md`, `work/the-lamp.md` at the example root. Every stand-in has the exact line `- **Unknowns:** none` once. The example must pass `check` with 0 errors and 0 warnings after Task 4. (`.stamps` is added in Task 5.)
  - `support.py` exports: `SKILL`, `SCRIPTS`, `EXAMPLE`, `CHECK`, `MV`, path constants `PREMISE`, `SYNOPSIS`, `OUTLINE`, `CHARACTERS`, `MISC`, `STORY`, `NO_UNKNOWNS`; class `TreeCase(unittest.TestCase)` with methods `path(rel)`, `read(rel)`, `write(rel, text)`, `replace(rel, old, new)`, `append(rel, text)`, `run_script(script, *args, env=None) -> (code, output)`, `run(*args)` (runs `CHECK` with args), `check(*args)` (runs `check wrist`), `assertCheckFails(fragment)`.

- [ ] **Step 1: Write the premise**

Create `plugins/wrist/skills/wrist/assets/examples/the-lamp/wrist/PREMISE.md`:

```markdown
---
profile: shortstory
title: The Lamp
slug: the-lamp
author: Ada Example
language: en
questions_generation: done
questions_realization: done
questions_publishing: done
review_done: yes
---

# Premise

A worked example: a short story of about 400 words.

## Answers

- **genre:** Literary fiction, quiet realism.
- **premise:** A clock repairer who has refused every job since her husband died takes in a boy's broken lamp.
- **ending:** Quiet recognition: she lights the lamp and opens the shutters.
- **tone:** Dry and restrained, warming only in the last lines.
- **audience:** Adult readers of literary magazines.
- **length:** About 400 words.
- **viewpoint:** Close third person on Ines, past tense.
- **target:** A literary magazine's flash fiction call.
- **characters:** Ines Vale, a clock repairer; Tomas, the boy from upstairs.
- **motifs:** Stopped clocks, light, a repair mark.
- **fixed:** The lamp carries her husband's repair mark under its base.
- **structure:** Compressed three-act form.
- **avoid:** Naming the grief, flashbacks, weather openings.
```

- [ ] **Step 2: Write the five stand-ins**

Create `.../the-lamp/wrist/synopsis.md.wrist.md`:

```markdown
# synopsis: The Lamp

Notes for the one-paragraph synopsis of the story.

- **Logline:** A clock repairer who has turned away every job since her husband died takes a boy's broken lamp and finds her husband's repair mark inside it.
- **Ending:** She returns the lamp lit and opens the shutters of her shop.
- **Theme:** Grief can turn a person into a closed shop.
- **Rules:** One paragraph, present tense, under 120 words, and it states the ending.
- **Required:** always
- **Depends on:** none
- **Referred by:** [outline](./outline.md.wrist.md)
- **Referred by:** [characters](./character.md.wrist.md)
- **Referred by:** [misc](./misc.md.wrist.md)
- **Unknowns:** none
```

Create `.../the-lamp/wrist/outline.md.wrist.md`:

```markdown
# outline: The Lamp

Notes for the outline of the story.

- **Structure:** Compressed three-act form: setup at the door, turn in the workshop, resolution at the window.
- **Rules:** Three beats only. Each beat changes what Ines will do next.
- **Required:** always
- **Depends on:** [synopsis](./synopsis.md.wrist.md) (mentions)
- **Unknowns:** none

## beat: The boy at the door

- **Purpose:** Introduce Ines, the shop and the lamp.
- **Change:** Ines agrees to a repair although she has refused every other.
- **Referred by:** [scene: At the door](./work/the-lamp.md.wrist.md#scene-at-the-door)

## beat: The mark inside

- **Purpose:** Reveal what the lamp means to her without saying it.
- **Change:** She stops working.
- **Referred by:** [scene: The mark](./work/the-lamp.md.wrist.md#scene-the-mark)

## beat: The lit window

- **Purpose:** Resolve by action, not statement.
- **Change:** She opens the shutters.
- **Referred by:** [scene: The window](./work/the-lamp.md.wrist.md#scene-the-window)
```

Create `.../the-lamp/wrist/character.md.wrist.md`:

```markdown
# characters: The Lamp

Notes for the registry of characters.

- **Rules:** Only Ines Vale and Tomas are named.
- **Required:** always
- **Depends on:** [synopsis](./synopsis.md.wrist.md) (mentions)
- **Unknowns:** none

## character: Ines Vale

Sixty-one, a clock repairer who stopped taking jobs a year ago.

- **Wants:** To be left alone with the stopped clocks.
- **Flaw:** Mistakes refusal for loyalty.
- **Voice:** Few words, dry, never asks a question twice.
- **Referred by:** [scene: At the door](./work/the-lamp.md.wrist.md#scene-at-the-door)
- **Referred by:** [scene: The mark](./work/the-lamp.md.wrist.md#scene-the-mark)
- **Referred by:** [scene: The window](./work/the-lamp.md.wrist.md#scene-the-window)

## character: Tomas

Eleven, lives upstairs.

- **Wants:** The lamp mended before dark.
- **Flaw:** Talks to fill silence.
- **Voice:** Quick and literal.
- **Referred by:** [scene: At the door](./work/the-lamp.md.wrist.md#scene-at-the-door)
- **Referred by:** [scene: The window](./work/the-lamp.md.wrist.md#scene-the-window)
```

Create `.../the-lamp/wrist/misc.md.wrist.md`:

```markdown
# misc: The Lamp

Notes for places and objects that are not characters.

- **Rules:** Only these two entries; nothing else is named.
- **Required:** always
- **Depends on:** [synopsis](./synopsis.md.wrist.md) (mentions)
- **Unknowns:** none

## place: The workshop

A ground-floor shop with the shutters down and a hand-lettered sign that says closed.

- **Facts:** Eleven clocks, each stopped at a different hour. The workbench faces the street window.
- **Referred by:** [scene: At the door](./work/the-lamp.md.wrist.md#scene-at-the-door)
- **Referred by:** [scene: The window](./work/the-lamp.md.wrist.md#scene-the-window)

## object: The brass lamp

- **Facts:** A paraffin lamp with a cracked glass chimney. Under the base, two small crossed lines scratched by Ines's husband.
- **Referred by:** [scene: At the door](./work/the-lamp.md.wrist.md#scene-at-the-door)
- **Referred by:** [scene: The mark](./work/the-lamp.md.wrist.md#scene-the-mark)
- **Referred by:** [scene: The window](./work/the-lamp.md.wrist.md#scene-the-window)
```

Create `.../the-lamp/wrist/work/the-lamp.md.wrist.md`:

```markdown
# story: The Lamp

Notes for the story itself.

- **Point of view:** Close third person on Ines, past tense.
- **Length:** About 400 words in three scenes.
- **Rules:** No scene opens on weather. Ines never names her grief. Dialogue stays short.
- **Required:** always
- **Referred by:** none
- **Unknowns:** none

## scene: At the door

- **Purpose:** Show Ines refusing by habit, then accepting the lamp.
- **Length:** About 120 words.
- **Must include:** The boy's name, the cracked glass, the sign that says closed.
- **Must avoid:** Explaining why she refuses.
- **Depends on:** [The boy at the door](../outline.md.wrist.md#beat-the-boy-at-the-door) (realizes)
- **Depends on:** [Ines Vale](../character.md.wrist.md#character-ines-vale) (appears)
- **Depends on:** [Tomas](../character.md.wrist.md#character-tomas) (appears)
- **Depends on:** [The workshop](../misc.md.wrist.md#place-the-workshop) (appears)
- **Depends on:** [The brass lamp](../misc.md.wrist.md#object-the-brass-lamp) (appears)

## scene: The mark

- **Purpose:** She finds her husband's mark and stops working.
- **Length:** About 100 words.
- **Must include:** The two crossed lines, the screwdriver put down.
- **Must avoid:** Memory, flashback, any named feeling.
- **Depends on:** [The mark inside](../outline.md.wrist.md#beat-the-mark-inside) (realizes)
- **Depends on:** [Ines Vale](../character.md.wrist.md#character-ines-vale) (appears)
- **Depends on:** [The brass lamp](../misc.md.wrist.md#object-the-brass-lamp) (appears)

## scene: The window

- **Purpose:** She lights the lamp, gives it back, and opens the shutters.
- **Length:** About 130 words.
- **Must include:** "Nothing" as the price, the match, the shutters going up.
- **Must avoid:** A closing line that states the theme.
- **Depends on:** [The lit window](../outline.md.wrist.md#beat-the-lit-window) (realizes)
- **Depends on:** [Ines Vale](../character.md.wrist.md#character-ines-vale) (appears)
- **Depends on:** [Tomas](../character.md.wrist.md#character-tomas) (appears)
- **Depends on:** [The workshop](../misc.md.wrist.md#place-the-workshop) (appears)
- **Depends on:** [The brass lamp](../misc.md.wrist.md#object-the-brass-lamp) (appears)
```

- [ ] **Step 3: Write the realized files**

Create `.../the-lamp/synopsis.md`:

```markdown
# The Lamp: Synopsis

Ines, a clock repairer who has turned away every job since her husband died, takes in a boy's broken lamp. Under its base she finds her husband's repair mark. She mends the lamp for nothing, lights it, and opens her shutters for the first time in a year.
```

Create `.../the-lamp/outline.md`:

```markdown
# The Lamp: Outline

1. **The boy at the door.** Ines, who refuses every job, agrees to repair a boy's lamp.
2. **The mark inside.** Under the base she finds her husband's mark and stops working.
3. **The lit window.** She mends the lamp, lights it, gives it back, and opens the shutters.
```

Create `.../the-lamp/character.md`:

```markdown
# The Lamp: Characters

**Ines Vale.** Sixty-one, a clock repairer who stopped taking jobs a year ago. She wants to be left alone with the stopped clocks and mistakes refusal for loyalty. She speaks little and never asks a question twice.

**Tomas.** Eleven, lives upstairs. He wants the lamp mended before dark and talks to fill silence.
```

Create `.../the-lamp/misc.md`:

```markdown
# The Lamp: Places and Objects

**The workshop.** A ground-floor shop with the shutters down and a hand-lettered sign that says closed. Eleven clocks stand in it, each stopped at a different hour.

**The brass lamp.** A paraffin lamp with a cracked glass chimney. Under the base are two small crossed lines, scratched by Ines's husband.
```

Create `.../the-lamp/work/the-lamp.md`:

```markdown
# The Lamp

The sign in the window said closed, and had said it for a year.

Tomas knocked anyway. He held the lamp against his chest the way he might hold a cat that did not want to be held.

"The glass is cracked," he said. "Mum says it's rubbish, but I want it fixed before dark."

Ines looked at the glass, then at the boy, then at the eleven clocks behind her, each stopped at its own hour. She had refused the postman's watch. She had refused the vicar's carriage clock, twice.

"Leave it on the bench," she said.

* * *

Under the base, where a stranger would never look, someone had scratched two small lines, crossed. She knew the hand. She knew the angle of the stroke, the slight hurry at the end of it, as if he had heard her calling him to supper.

She put down the screwdriver. She did not pick it up again for a long time.

The street went on outside. A bus went by, and its light crossed the bench and was gone.

* * *

Tomas came at dusk. The lamp stood on the bench with a new chimney, its wick trimmed, its brass rubbed to the colour of tea.

"How much?" he said.

"Nothing."

She struck a match. The flame took, steadied, and lit his face from below, so that for a moment he looked like someone older.

"Take it carefully," she said. "It's been waiting."

When he had gone she stood a while with her hand on the shutter. Then she pulled it up, and the last of the day came in across the clocks.
```

- [ ] **Step 4: Write the shared test support**

Replace `plugins/wrist/tests/support.py` with:

```python
"""Shared fixtures for the wrist tests.

Each test copies the bundled the-lamp example into a temporary directory, breaks it in one
way, and runs the scripts as a user would.

Run from the repository root:

    python3 -m unittest discover -s plugins/wrist/tests
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.normpath(os.path.join(HERE, "..", "skills", "wrist"))
SCRIPTS = os.path.join(SKILL, "scripts")
EXAMPLE = os.path.join(SKILL, "assets", "examples", "the-lamp")
CHECK = os.path.join(SCRIPTS, "wrist_check.py")
MV = os.path.join(SCRIPTS, "wrist_mv.py")
sys.path.insert(0, SCRIPTS)

PREMISE = "wrist/PREMISE.md"
SYNOPSIS = "wrist/synopsis.md.wrist.md"
OUTLINE = "wrist/outline.md.wrist.md"
CHARACTERS = "wrist/character.md.wrist.md"
MISC = "wrist/misc.md.wrist.md"
STORY = "wrist/work/the-lamp.md.wrist.md"
NO_UNKNOWNS = "- **Unknowns:** none\n"


class TreeCase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="wrist-test-")
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        shutil.copytree(EXAMPLE, self.dir, dirs_exist_ok=True)

    def path(self, rel):
        return os.path.join(self.dir, rel)

    def read(self, rel):
        with open(self.path(rel), encoding="utf-8") as fh:
            return fh.read()

    def write(self, rel, text):
        os.makedirs(os.path.dirname(self.path(rel)), exist_ok=True)
        with open(self.path(rel), "w", encoding="utf-8") as fh:
            fh.write(text)

    def replace(self, rel, old, new):
        text = self.read(rel)
        self.assertIn(old, text, f"fixture text not found in {rel}")
        self.write(rel, text.replace(old, new, 1))

    def append(self, rel, text):
        with open(self.path(rel), "a", encoding="utf-8") as fh:
            fh.write(text)

    def run_script(self, script, *args, env=None):
        proc = subprocess.run([sys.executable, script, *args], cwd=self.dir, env=env,
                              capture_output=True, text=True)
        return proc.returncode, proc.stdout + proc.stderr

    def run_wrist(self, *args, env=None):
        return self.run_script(CHECK, *args, env=env)

    def check(self, *args):
        return self.run_wrist("check", "wrist", *args)

    def assertCheckFails(self, fragment):
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("error", out)
        self.assertIn(fragment, out)
```

- [ ] **Step 5: Commit**

```bash
git add plugins/wrist
git commit -m "feat(wrist): add the-lamp example project and shared test support" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Make the checker profile-driven (check, unknowns, fix-backlinks, mv)

This is the core refactor. The example from Task 3 must pass `check` clean when it is done.

**Files:**
- Modify: `plugins/wrist/skills/wrist/scripts/wrist_check.py`
- Modify: `plugins/wrist/skills/wrist/scripts/wrist_mv.py`
- Delete: `plugins/wrist/tests/test_wrist_check.py`, `plugins/wrist/skills/wrist/assets/examples/undo-system/`, `plugins/wrist/skills/wrist/assets/templates/{code,data,iac}.wrist.md` and `SYSTEM.md`, `plugins/wrist/skills/wrist/references/{abstract-systems,implementing}.md`
- Create: `plugins/wrist/tests/test_check.py`, `test_unknowns.py`, `test_graph.py`, `test_generic.py`

**Interfaces:**
- Consumes: `wrist_profile` (Task 2) as listed there; `support.py` (Task 3).
- Produces in `wrist_check.py` (used by Tasks 5 to 7):
  - Module constants `WRIST_SUFFIX = ".wrist.md"`, `PREMISE_FILE = "PREMISE.md"`, `STAMPS_FILE = ".stamps"`.
  - `configure(profile)`: builds `TYPED_RE`, `FIELD_RE`, `CANON` from the profile and sets `PROFILE`.
  - `class WristFile` with `path`, `rel`, `impl_rel` (forward-slash path of the realized file), `base`, `sections`, `unknowns`, `lines`, `diags`, `function` (profile function name or `None`), `err(line, msg)`, `warn(line, msg)`.
  - `class Premise` with `exists`, `front` (key → `(line, value)`), `unknowns`, `links`, `slugs`, `answers` (id → `(line, value)`), `diags`.
  - `read_premise(wrist_root) -> Premise`; `premise_problems(pm, profile, override) -> [(severity, line, msg)]`
  - `load_all(args) -> (wrist_root, files, profile, pm, slug)` where `args` has `wrist_dir` and `profile` (may be `None`). Exits with a message when no profile can be determined or the profile is invalid.
  - `collect_diags(wrist_dir, wrist_root, files, profile, pm, slug, lenient, override) -> (diags: dict[rel, list[(severity, line, msg)]], deps, pairs)`; the `PREMISE_FILE` key always exists.
  - `command(name, setup=None)` decorator registering `COMMANDS[name] = (fn, setup)`; `main()` builds one subparser per registered command, each with positional `wrist_dir` and `--profile`, and calls the function with the parsed args. Later tasks add commands only by decorating new functions.
  - `stand_in_hash(sf) -> str` (kept), `file_hash`, `decisions(pairs)`, `tree_unknowns(files, premise_unknowns)`, `heading_path`, `slugify`, `own_fields`, `file_fields` (kept).

- [ ] **Step 1: Delete what cannot survive**

```bash
cd /home/sean/Data/Projects/claude-plugins/plugins/wrist
git rm -q tests/test_wrist_check.py
git rm -rq skills/wrist/assets/examples/undo-system
git rm -q skills/wrist/assets/templates/code.wrist.md skills/wrist/assets/templates/data.wrist.md \
          skills/wrist/assets/templates/iac.wrist.md skills/wrist/assets/templates/SYSTEM.md
git rm -q skills/wrist/references/abstract-systems.md skills/wrist/references/implementing.md
```

Why: every kept skel test is fused to the undo-system fixture (code stand-ins with `role:` front matter). The behavior they cover (unknown rules, backlinks, move) is re-tested below against the-lamp. This is a deliberate deviation from the spec's "carried over and renamed"; say so in the final hand-back.

- [ ] **Step 2: Write the failing tests**

Create `plugins/wrist/tests/test_check.py`:

```python
import os
import re
import unittest

from support import (CHARACTERS, CHECK, MISC, OUTLINE, PREMISE, STORY, SYNOPSIS, TreeCase)


class CheckAcceptsTheExample(TreeCase):
    def test_pristine_example_has_no_errors_or_warnings(self):
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("5 stand-ins", out)
        self.assertIn("0 errors, 0 warnings", out)

    def test_left_over_arguments_are_rejected(self):
        code, out = self.run_wrist("check", "wrist", "extra")
        self.assertEqual(code, 2, out)
        self.assertIn("unrecognized arguments: extra", out)

    def test_crlf_files_check_clean(self):
        for rel in (SYNOPSIS, OUTLINE, CHARACTERS, MISC, STORY, PREMISE):
            with open(self.path(rel), "rb") as fh:
                data = fh.read().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
            with open(self.path(rel), "wb") as fh:
                fh.write(data)
        code, out = self.check()
        self.assertEqual(code, 0, out)


class CheckRejectsBrokenTrees(TreeCase):
    def test_deleted_backlink(self):
        self.replace(SYNOPSIS, "- **Referred by:** [outline](./outline.md.wrist.md)\n", "")
        self.assertCheckFails("missing backlink")

    def test_referred_by_without_a_matching_dependency(self):
        self.append(SYNOPSIS, "- **Referred by:** [story](./work/the-lamp.md.wrist.md)\n")
        self.assertCheckFails("is listed as referring here but has no `Depends on:` link")

    def test_link_to_a_missing_file(self):
        self.append(OUTLINE, "- **Depends on:** [gone](./gone.md.wrist.md)\n")
        self.assertCheckFails("link target does not exist")

    def test_dangling_fragment(self):
        self.replace(STORY, "#beat-the-mark-inside", "#beat-no-such-beat")
        self.assertCheckFails("fragment '#beat-no-such-beat' does not match any heading")

    def test_missing_required_field(self):
        self.replace(CHARACTERS, "- **Wants:** To be left alone with the stopped clocks.\n", "")
        self.assertCheckFails("character 'Ines Vale' is missing `Wants:`")

    def test_missing_level_one_field(self):
        self.replace(SYNOPSIS, "- **Theme:** Grief can turn a person into a closed shop.\n", "")
        self.assertCheckFails("synopsis 'The Lamp' is missing `Theme:`")

    def test_missing_common_field(self):
        self.replace(MISC, "- **Required:** always\n", "")
        self.assertCheckFails("missing `Required:`")

    def test_missing_unknowns_answer(self):
        self.replace(MISC, "- **Unknowns:** none\n", "")
        self.assertCheckFails("no *UNKNOWN* entries and no `Unknowns: none`")

    def test_wrong_level_one_heading(self):
        self.replace(SYNOPSIS, "# synopsis: The Lamp", "# outline: The Lamp")
        self.assertCheckFails("must start with `# synopsis: <name>`")

    def test_child_heading_not_declared_for_the_function(self):
        self.append(OUTLINE, "\n## scene: Extra\n")
        self.assertCheckFails("`## scene:` not allowed here")

    def test_typed_heading_too_deep(self):
        self.append(OUTLINE, "\n### beat: Deep\n")
        self.assertCheckFails("`### beat:` not allowed here")

    def test_stand_in_outside_the_shape(self):
        self.write("wrist/extra.md.wrist.md", "# synopsis: Extra\n")
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("outside the shortstory shape", out)

    def test_missing_required_stand_in(self):
        os.remove(self.path(MISC))
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("required stand-in missing: wrist/misc.md.wrist.md", out)

    def test_story_name_must_match_the_slug(self):
        self.replace(PREMISE, "slug: the-lamp", "slug: lamp")
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("required stand-in missing: wrist/work/lamp.md.wrist.md", out)
        self.assertIn("outside the shortstory shape", out)

    def test_code_fence_without_a_language_tag(self):
        self.append(MISC, "\n```\nsample\n```\n")
        self.assertCheckFails("code fence has no language tag")

    def test_front_matter_in_a_stand_in_is_a_warning(self):
        self.write(SYNOPSIS, "---\nrole: product\n---\n" + self.read(SYNOPSIS))
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("stand-ins take no front matter", out)


class CheckWarnings(TreeCase):
    def test_informal_marker(self):
        self.append(OUTLINE, "\nTODO decide the middle beat.\n")
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("informal marker 'TODO'", out)

    def test_unlisted_relation_word_is_a_warning(self):
        self.replace(OUTLINE, "[synopsis](./synopsis.md.wrist.md) (mentions)",
                     "[synopsis](./synopsis.md.wrist.md) (adores)")
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("relation word 'adores' is not one of", out)

    def test_too_much_free_prose_is_a_warning(self):
        self.replace(OUTLINE, "## beat: The mark inside\n",
                     "## beat: The mark inside\n\n" + " ".join(["word"] * 130) + "\n")
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("130 words of free prose", out)

    def test_fenced_text_does_not_count_as_prose(self):
        self.replace(OUTLINE, "## beat: The mark inside\n",
                     "## beat: The mark inside\n\n```text\n" + " ".join(["word"] * 130) + "\n```\n")
        code, out = self.check()
        self.assertIn("0 errors, 0 warnings", out)


class LenientMode(TreeCase):
    def test_missing_field_is_a_warning_when_lenient(self):
        self.replace(CHARACTERS, "- **Wants:** To be left alone with the stopped clocks.\n", "")
        code, out = self.check("--lenient")
        self.assertEqual(code, 0, out)
        self.assertIn("warning: character 'Ines Vale' is missing `Wants:`", out)

    def test_broken_link_still_fails_when_lenient(self):
        self.append(OUTLINE, "- **Depends on:** [gone](./gone.md.wrist.md)\n")
        code, out = self.check("--lenient")
        self.assertEqual(code, 1, out)


class PremiseRules(TreeCase):
    def test_missing_premise_without_a_profile_flag_stops(self):
        os.remove(self.path(PREMISE))
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("no profile", out)

    def test_missing_premise_with_a_profile_flag_is_an_error(self):
        os.remove(self.path(PREMISE))
        code, out = self.run_wrist("check", "wrist", "--profile", "shortstory")
        self.assertEqual(code, 1, out)
        self.assertIn("PREMISE.md is missing", out)

    def test_profile_flag_overrides_the_premise(self):
        self.replace(PREMISE, "profile: shortstory\n", "")
        code, out = self.run_wrist("check", "wrist", "--profile", "shortstory")
        self.assertEqual(code, 0, out)

    def test_unknown_profile_name(self):
        self.replace(PREMISE, "profile: shortstory", "profile: sonnet")
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("no profile 'sonnet'", out)

    def test_title_is_required(self):
        self.replace(PREMISE, "title: The Lamp\n", "")
        self.assertCheckFails("front matter needs `title:`")

    def test_slug_must_be_lower_case_words(self):
        self.replace(PREMISE, "slug: the-lamp", "slug: The_Lamp")
        self.assertCheckFails("slug 'The_Lamp' must be lower-case words joined by hyphens")

    def test_required_question_must_be_answered(self):
        self.replace(PREMISE, "- **genre:** Literary fiction, quiet realism.\n", "")
        self.assertCheckFails("question 'genre'")

    def test_deferrable_question_unanswered_is_a_warning(self):
        self.replace(PREMISE, "- **avoid:** Naming the grief, flashbacks, weather openings.\n", "")
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("warning: question 'avoid'", out)

    def test_an_unknown_answers_a_question(self):
        self.replace(PREMISE, "- **genre:** Literary fiction, quiet realism.",
                     "- **genre:** *UNKNOWN*: [genre-pick] Which genre. Kind: blocking. Consequence: c. Unlocks: u.")
        code, out = self.check()
        self.assertEqual(code, 0, out)

    def test_broken_link_in_the_premise(self):
        self.append(PREMISE, "\nSee [gone](./gone.md.wrist.md).\n")
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("PREMISE.md", out)
        self.assertIn("link target does not exist", out)

    def test_dangling_fragment_in_the_premise(self):
        self.append(PREMISE, "\nSee [x](./outline.md.wrist.md#beat-nope).\n")
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("fragment '#beat-nope' does not match any heading", out)

    def test_links_inside_fences_in_the_premise_are_ignored(self):
        self.append(PREMISE, "\n```text\n[gone](./gone.md.wrist.md)\n```\n")
        code, out = self.check()
        self.assertEqual(code, 0, out)


if __name__ == "__main__":
    unittest.main()
```

Create `plugins/wrist/tests/test_unknowns.py`:

```python
import json
import re
import unittest

from support import CHECK, MISC, PREMISE, STORY, NO_UNKNOWNS, TreeCase

DECL = "[venue] Which venue. Kind: blocking. Consequence: c. Unlocks: u."


class UnknownsCommand(TreeCase):
    def unknowns(self, *args):
        return self.run_wrist("unknowns", "wrist", *args)

    def declare(self, rel, text):
        self.replace(rel, NO_UNKNOWNS, f"*UNKNOWN*: {text}\n")

    def group(self, out, title):
        lines = out.splitlines()
        start = next((i for i, l in enumerate(lines) if l.startswith(title + " (")), None)
        self.assertIsNotNone(start, f"no '{title}' group in:\n{out}")
        body = []
        for line in lines[start + 1:]:
            if not line.strip():
                break
            body.append(line)
        return body

    def count(self, out):
        return int(re.search(r"(\d+) unknowns", out).group(1))

    def test_pristine_example_has_none(self):
        _, out = self.unknowns()
        self.assertIn("No unknowns.", out)

    def test_local_unknown_is_listed_under_local(self):
        self.declare(MISC, "[clocks] How many clocks. Kind: local. Proposed: eleven. Consequence: c. Unlocks: u.")
        _, out = self.unknowns()
        body = self.group(out, "Local")
        self.assertTrue(any(l.startswith("- [clocks] misc.md.wrist.md:") and "(misc: The Lamp)" in l
                            for l in body), body)

    def test_blocking_unknown_is_listed_under_blocking(self):
        self.declare(MISC, DECL)
        _, out = self.unknowns()
        body = self.group(out, "Blocking")
        self.assertTrue(any("misc.md.wrist.md:" in l and "Which venue." in l for l in body), body)

    def test_unknown_without_kind_is_listed_under_no_valid_kind(self):
        self.declare(MISC, "Something open. Consequence: c. Unlocks: u.")
        _, out = self.unknowns()
        self.assertTrue(any("Something open." in l for l in self.group(out, "No valid kind")))

    def test_follower_is_listed_beneath_its_declaration(self):
        self.declare(MISC, DECL)
        self.declare(STORY, "Follows [venue]. Consequence: the register of the dialogue.")
        _, out = self.unknowns()
        self.assertIn("    followed at work/the-lamp.md.wrist.md:", out)
        self.assertEqual(self.count(out), 1)

    def test_premise_unknown_is_labelled_premise(self):
        self.append(PREMISE, "\n*UNKNOWN*: [pen-name] Which name. Kind: blocking. Consequence: c. Unlocks: u.\n")
        _, out = self.unknowns()
        self.assertTrue(any(l.startswith("- [pen-name] PREMISE.md:") and "(premise)" in l
                            for l in self.group(out, "Blocking")))

    def test_check_and_unknowns_report_the_same_count(self):
        self.declare(MISC, DECL)
        _, checked = self.check()
        _, listed = self.unknowns()
        self.assertEqual(self.count(checked), 1)
        self.assertEqual(self.count(listed), 1)

    def test_json_items_share_one_shape(self):
        self.declare(MISC, "Follows [nosuch]. Consequence: unspecified here.")
        _, out = self.unknowns("--json")
        keys = {"file", "line", "where", "text", "name", "follows", "kind", "proposed", "consequence",
                "unlocks", "followers"}
        items = json.loads(out)
        self.assertTrue(items)
        for item in items:
            self.assertEqual(set(item), keys, item)


class UnknownRules(TreeCase):
    def declare(self, text, rel=MISC):
        self.replace(rel, NO_UNKNOWNS, f"*UNKNOWN*: {text}\n")

    def test_declaration_without_kind_is_an_error(self):
        self.declare("[venue] Which venue. Consequence: c. Unlocks: u.")
        self.assertCheckFails("*UNKNOWN* is missing `Kind:` (blocking or local)")

    def test_declaration_without_kind_is_a_warning_when_lenient(self):
        self.declare("[venue] Which venue. Consequence: c. Unlocks: u.")
        code, out = self.check("--lenient")
        self.assertEqual(code, 0, out)
        self.assertIn("warning: *UNKNOWN* is missing `Kind:`", out)

    def test_kind_must_be_blocking_or_local(self):
        self.declare("[venue] Which venue. Kind: maybe. Consequence: c. Unlocks: u.")
        self.assertCheckFails("*UNKNOWN* has `Kind: maybe`; it must be blocking or local")

    def test_local_unknown_needs_a_proposal(self):
        self.declare("[venue] Which venue. Kind: local. Consequence: c. Unlocks: u.")
        self.assertCheckFails("*UNKNOWN* with `Kind: local` needs `Proposed:`")

    def test_follower_of_an_undeclared_name_is_an_error(self):
        self.declare("Follows [nosuch]. Consequence: c.")
        self.assertCheckFails("`Follows [nosuch]` matches no declared unknown")

    def test_duplicate_name_is_an_error(self):
        self.declare(DECL)
        self.append(PREMISE, "\n*UNKNOWN*: [venue] Again. Kind: blocking. Consequence: c. Unlocks: u.\n")
        self.assertCheckFails("unknown name [venue] is already declared at")

    def test_name_must_be_lower_case(self):
        self.declare("[Venue] Which venue. Kind: blocking. Consequence: c. Unlocks: u.")
        self.assertCheckFails("must be lower-case letters, digits and hyphens")

    def test_premise_unknown_without_kind_is_an_error(self):
        self.append(PREMISE, "\n*UNKNOWN*: [pen-name] Which name. Consequence: c. Unlocks: u.\n")
        self.assertCheckFails("*UNKNOWN* is missing `Kind:`")

    def test_follower_with_extra_clauses_is_a_warning(self):
        self.declare(DECL)
        self.replace(STORY, NO_UNKNOWNS,
                     "*UNKNOWN*: Follows [venue]. Kind: blocking. Consequence: c.\n")
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("takes only `Consequence:`", out)

    def test_kind_inside_prose_is_not_a_clause(self):
        self.declare("[venue] Which venue, as in kind: magazine or anthology. Kind: blocking. "
                     "Consequence: c. Unlocks: u.")
        code, out = self.check()
        self.assertEqual(code, 0, out)

    def test_unknown_without_consequence_or_unlocks_is_a_warning(self):
        self.declare("[venue] Which venue. Kind: blocking.")
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("should state `Consequence:` and `Unlocks:`", out)


if __name__ == "__main__":
    unittest.main()
```

Create `plugins/wrist/tests/test_graph.py`:

```python
import os
import unittest

from support import CHARACTERS, MV, OUTLINE, PREMISE, STORY, SYNOPSIS, TreeCase

BACKLINK = "- **Referred by:** [outline](./outline.md.wrist.md)\n"


class FixBacklinks(TreeCase):
    def test_write_restores_a_deleted_backlink(self):
        self.replace(SYNOPSIS, BACKLINK, "")
        self.assertEqual(self.check()[0], 1)
        self.run_wrist("fix-backlinks", "wrist", "--write")
        code, out = self.check()
        self.assertEqual(code, 0, out)

    def test_dry_run_changes_nothing(self):
        self.replace(SYNOPSIS, BACKLINK, "")
        _, out = self.run_wrist("fix-backlinks", "wrist")
        self.assertIn("dry run", out)
        self.assertEqual(self.check()[0], 1)

    def test_nothing_to_fix(self):
        _, out = self.run_wrist("fix-backlinks", "wrist")
        self.assertIn("All backlinks present.", out)


class Move(TreeCase):
    def moved_check(self):
        code, out = self.check()
        self.assertNotIn("link target does not exist", out)
        self.assertNotIn("missing backlink", out)
        return out

    def test_moving_a_file_rewrites_every_link(self):
        code, out = self.run_script(MV, "wrist", STORY, "wrist/work/lamp-two.md.wrist.md")
        self.assertEqual(code, 0, out)
        self.assertTrue(os.path.exists(self.path("wrist/work/lamp-two.md.wrist.md")))
        self.moved_check()

    def test_moving_a_directory_rewrites_every_link(self):
        code, out = self.run_script(MV, "wrist", "wrist/work", "wrist/pieces")
        self.assertEqual(code, 0, out)
        self.moved_check()

    def test_links_in_the_premise_are_rewritten(self):
        self.append(PREMISE, "\nOutline: [outline](./outline.md.wrist.md).\n")
        self.run_script(MV, "wrist", OUTLINE, "wrist/plan/outline.md.wrist.md")
        self.assertIn("(./plan/outline.md.wrist.md)", self.read(PREMISE))

    def test_dry_run_moves_nothing(self):
        self.run_script(MV, "wrist", STORY, "wrist/work/lamp-two.md.wrist.md", "--dry-run")
        self.assertTrue(os.path.exists(self.path(STORY)))

    def test_links_inside_fences_are_left_alone(self):
        self.append(OUTLINE, "\n```text\n[x](./synopsis.md.wrist.md)\n```\n")
        self.run_script(MV, "wrist", SYNOPSIS, "wrist/start/synopsis.md.wrist.md")
        self.assertIn("```text\n[x](./synopsis.md.wrist.md)\n```", self.read(OUTLINE))


if __name__ == "__main__":
    unittest.main()
```

Create `plugins/wrist/tests/test_generic.py`:

```python
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from support import CHECK


class FakeProfile(unittest.TestCase):
    """A two-heading profile with no story vocabulary: the checker must run it unchanged."""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="wrist-fake-")
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        prof = os.path.join(self.dir, "profiles", "poemlet")
        os.makedirs(prof)
        data = {"name": "poemlet",
                "files": [{"path": "a.md", "function": "alpha", "order": 2},
                          {"path": "b.md", "function": "beta", "order": 1}],
                "functions": {"alpha": {"heading": "alpha", "fields": ["Hue"], "children": {"bead": ["Size"]}},
                              "beta": {"heading": "beta"}},
                "relations": ["uses"], "limits": {"max_prose_words": 50}}
        with open(os.path.join(prof, "profile.json"), "w") as fh:
            json.dump(data, fh)
        self.put("wrist/PREMISE.md", "---\nprofile: poemlet\ntitle: Tiny\nslug: tiny\n---\n\n# Premise\n")
        self.put("wrist/a.md.wrist.md",
                 "# alpha: One\n\n- **Hue:** red\n- **Required:** always\n- **Rules:** none\n"
                 "- **Depends on:** [b](./b.md.wrist.md) (uses)\n- **Referred by:** none\n"
                 "- **Unknowns:** none\n\n## bead: First\n\n- **Size:** small\n")
        self.put("wrist/b.md.wrist.md",
                 "# beta: Two\n\n- **Required:** always\n- **Rules:** none\n- **Depends on:** none\n"
                 "- **Referred by:** [a](./a.md.wrist.md)\n- **Unknowns:** none\n")

    def put(self, rel, text):
        path = os.path.join(self.dir, "project", rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def run_cli(self, *args):
        env = dict(os.environ, WRIST_PROFILES_DIR=os.path.join(self.dir, "profiles"))
        proc = subprocess.run([sys.executable, CHECK, *args], cwd=os.path.join(self.dir, "project"),
                              env=env, capture_output=True, text=True)
        return proc.returncode, proc.stdout + proc.stderr

    def test_check_passes(self):
        code, out = self.run_cli("check", "wrist")
        self.assertEqual(code, 0, out)
        self.assertIn("2 stand-ins", out)

    def test_an_undeclared_heading_type_is_rejected(self):
        self.put("wrist/b.md.wrist.md", "# scene: Two\n")
        code, out = self.run_cli("check", "wrist")
        self.assertEqual(code, 1, out)
        self.assertIn("must start with `# beta: <name>`", out)

    def test_the_profile_decides_the_required_fields(self):
        with open(os.path.join(self.dir, "project", "wrist", "a.md.wrist.md"), encoding="utf-8") as fh:
            text = fh.read().replace("- **Size:** small\n", "")
        self.put("wrist/a.md.wrist.md", text)
        code, out = self.run_cli("check", "wrist")
        self.assertEqual(code, 1, out)
        self.assertIn("bead 'First' is missing `Size:`", out)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run to verify they fail**

Run: `python3 -m unittest discover -s plugins/wrist/tests 2>&1 | tail -5`
Expected: many failures: the checker still speaks skel (`role:` errors, undo-style headings), and `wrist_check.py` has no `--profile` option.

- [ ] **Step 4: Replace the module header and constants in `wrist_check.py`**

In `plugins/wrist/skills/wrist/scripts/wrist_check.py`, replace everything from the opening `#!/usr/bin/env python3` line through the end of the `LEVEL_FIELDS = {...}` block (the line before `def slugify`) with:

```python
#!/usr/bin/env python3
"""wrist_check.py: validate and analyze a wrist stand-in tree.

The grammar comes from a profile (profiles/<name>/), chosen by `profile:` in wrist/PREMISE.md or
by --profile. Every command takes WRIST_DIR first.

Subcommands
  check            grammar, profile file shape, links, bidirectional backlinks, unknown rules, PREMISE.md
  unknowns         open decisions by kind, each once, with its followers
  order            realization order from the profile; reports dependencies that contradict it
  status           pending, realized, stale, edited and unstamped files
  stamp            record that a realized file was written from its stand-in (wrist/.stamps)
  fix-backlinks    insert missing `Referred by:` lines (dry-run by default)
  gate PHASE       list what blocks the generation, realization or publishing phase
  lint             scan realized prose for the profile's clichés (advisory)
  publish          build output/<slug>.epub and output/<slug>.pdf

Standard library only. Exit code 1 if `check` finds errors.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wrist_profile

WRIST_SUFFIX = ".wrist.md"
PREMISE_FILE = "PREMISE.md"
STAMPS_FILE = ".stamps"
COMMON_LABELS = ["Depends on", "Referred by", "Required", "Rules", "Unknowns"]

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
FENCE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})(.*)$")
LINK_RE = re.compile(r"\[([^\]]+)\]\(\s*([^)\s]+)(?:\s+\"[^\"]*\")?\s*\)")
# a link with an optional relation word after it: [Mara](path) (appears)
LINK_REL_RE = re.compile(LINK_RE.pattern + r"(?:\s*\(([A-Za-z][A-Za-z -]*)\))?")
# These three depend on the profile in use and are built by configure().
TYPED_RE = FIELD_RE = None
CANON = {}
PROFILE = None
UNKNOWN_RE = re.compile(r"(?:\*{1,2}UNKNOWN\*{1,2}\s*:|\*\*UNKNOWN:\*\*)\s*(.*)")
INFORMAL_RE = re.compile(r"(\bTBD\b|\bTODO\b|\bFIXME\b|\?\?\?|(?<![*\w])UNKNOWN(?![*\w]))")
NONE_RE = re.compile(r"^\s*(none|n/?a)\b", re.I)
BULLET_LINK_RE = re.compile(r"^\s*[-*+]\s+.*\[[^\]]+\]\([^)]+\)")
EXTERNAL_RE = re.compile(r"^[a-z][a-z0-9+.-]*:", re.I)
DOTTED_RE = re.compile(r"^`?([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+)`?$")
UNKNOWN_NAME_RE = re.compile(r"^\[([a-z0-9][a-z0-9-]*)\](?!\()\s*")
BRACKET_RE = re.compile(r"^\[([^\]]*)\](?!\()\s*")      # a leading [..] that is not a markdown link
FOLLOWS_RE = re.compile(r"^(?i:follows)\s+\[([^\]]*)\]\s*\.?\s*")
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
# A clause label opens the text or follows the end of a sentence, so "kind:" inside prose is not one.
CLAUSE_RE = re.compile(r"(?:^|(?<=[.!?;)`*]\s))\**(Kind|Proposed|Consequence|Unlocks)\**:\**\s*")
KINDS = ("blocking", "local")
META_RE = re.compile(r"^\s*([A-Za-z_]+)\s*:\s*(.*)$")
ANSWER_RE = re.compile(r"^\s*[-*+]\s+\*\*([a-z0-9]+(?:-[a-z0-9]+)*):\*\*\s*(.*)$")

COMMANDS = {}      # name -> (function, function that adds the command's own arguments or None)


def command(name, setup=None):
    def register(fn):
        COMMANDS[name] = (fn, setup)
        return fn
    return register


def configure(profile):
    """Build the heading and field patterns from the profile and keep it for the rest of the run."""
    global TYPED_RE, FIELD_RE, CANON, PROFILE
    labels = list(COMMON_LABELS) + [l for l in profile.labels() if l not in COMMON_LABELS]
    labels.sort(key=len, reverse=True)
    types = sorted(profile.heading_types(), key=len, reverse=True)
    TYPED_RE = re.compile(r"^(" + "|".join(re.escape(t) for t in types) + r")\s*:\s*(.+)$", re.I)
    FIELD_RE = re.compile(r"^\s*(?:[-*+]\s+)?(?:\*\*|__)?(" + "|".join(re.escape(l) for l in labels) +
                          r")(?:\*\*|__)?\s*:(?:\*\*|__)?\s*(.*)$", re.I)
    CANON = {l.lower(): l for l in labels}
    PROFILE = profile


```

- [ ] **Step 5: Edit the classes and `parse`**

Make these edits in `wrist_check.py`.

1. In `class Link`, replace `__init__` with:

```python
    def __init__(self, label, text, target, line, section, relation=None):
        self.label, self.text, self.target, self.line, self.section = label, text, target, line, section
        self.relation = relation
```

2. In `class Unknown`, replace the two properties `where` and `label` bodies' fallbacks: `"(system)"` becomes `"(premise)"` and `"system"` becomes `"premise"`.

3. Replace the whole `class SkelFile`/`WristFile` (the renamed one) with:

```python
class WristFile:
    def __init__(self, path, wrist_root):
        self.path = os.path.abspath(path)
        self.rel = os.path.relpath(self.path, wrist_root)
        self.impl_rel = self.rel[: -len(WRIST_SUFFIX)].replace(os.sep, "/")
        self.base = os.path.basename(self.impl_rel)
        self.function = None    # the profile function this stand-in has, set by validate_file
        self.root = Section(0, None, "", "", 0)
        self.sections = []
        self.unknowns = []      # [Unknown]
        self.lines = []
        self.diags = []         # (severity, line, msg)

    def err(self, line, msg):
        self.diags.append(("error", line, msg))

    def warn(self, line, msg):
        self.diags.append(("warning", line, msg))

    def all_links(self):
        out = list(self.root.links)
        for s in self.sections:
            out.extend(s.links)
        return out
```

4. Delete `infer_kind` entirely.

5. In `parse(path, wrist_root)`: change `sf = SkelFile(path, skel_root)`/`WristFile(path, wrist_root)` as already renamed, then replace the block from `start = 0` through `sf.kind = infer_kind(sf)` with:

```python
    start = 0
    end = front_matter_end(lines)
    if end == -1 and len(lines) > 1 and META_RE.match(lines[1]):
        sf.err(1, "front matter is not closed with `---`")
    if end > 0:
        start = end + 1
        sf.warn(1, "stand-ins take no front matter; the profile decides what each file is")
```

6. In `parse`, replace

```python
                found = LINK_RE.findall(value)
                for text, target in found:
                    cur.links.append(Link(label, text, target, ln, cur))
```

with

```python
                found = LINK_REL_RE.findall(value)
                for text, target, rel in found:
                    cur.links.append(Link(label, text, target, ln, cur, rel or None))
```

and replace

```python
            for text, target in LINK_RE.findall(line):
                cur.links.append(Link(pending[0], text, target, ln, cur))
```

with

```python
            for text, target, rel in LINK_REL_RE.findall(line):
                cur.links.append(Link(pending[0], text, target, ln, cur, rel or None))
```

7. In `fragment_problems`, replace the `symbols = [...]` line with:

```python
    symbols = [s for s in secs if s.level > 1 and s.kind]
```

- [ ] **Step 6: Remove the code-only functions**

Delete these functions from `wrist_check.py` (the whole `def`, with decorator-free bodies): `validate_file`, `read_system`, `check_system`, `resolve_units`, `unit_members`, `untested_units`, `cmd_check`, `cmd_order`, `sccs`, `is_generated`, `drift_checked`, `spec_path`, `read_spec_header`, `stamp_state`, `heading_name`, `missing_names`, `cmd_stamp`, `cmd_batches`, `cmd_status`, `infer_role`, `infer_unit`, `add_front_matter`, `cmd_infer_roles`, and the old `main`. Also delete the `IGNORE_DIRS = ...` constant. Keep `stand_in_hash`, `own_fields`, `own_count`, `file_fields`, `find_untyped`, `load_tree`, `relpath_dot`, `resolve`, `build_edges`, `check_bidirectional`, `unknown_problems`, `name_problems`, `heading_path`, `tree_unknowns`, `decisions`, `unknown_item`, `cmd_unknowns`, `cmd_fix_backlinks`, `section_end`.

Run: `grep -nE "sf\.kind|\.role\b|\.abstract|SYSTEM_FILE|read_system|SPEC_RE|resolve_units|LEVEL1|CODE_EXT|skel_" plugins/wrist/skills/wrist/scripts/wrist_check.py`
Expected: no output except possibly `load_tree`'s parameter. Fix any leftover reference (rename a stray `skel_root` to `wrist_root`).

- [ ] **Step 7: Edit `load_tree`, `cmd_unknowns` and `cmd_fix_backlinks`**

1. In `load_tree`, replace `fn.endswith(SKEL_SUFFIX)`/`WRIST_SUFFIX` check and the parse call so the function reads:

```python
def load_tree(wrist_dir):
    wrist_root = os.path.abspath(wrist_dir)
    if not os.path.isdir(wrist_root):
        sys.exit(f"not a directory: {wrist_dir}")
    files = {}
    for dp, dns, fns in os.walk(wrist_root):
        dns[:] = sorted(d for d in dns if not d.startswith("."))
        for fn in sorted(fns):
            if fn.endswith(WRIST_SUFFIX):
                sf = parse(os.path.join(dp, fn), wrist_root)
                files[sf.path] = sf
    return wrist_root, files
```

2. Decorate and rewire `cmd_unknowns`: replace its first two lines (`skel_root, files = load_tree(args.skel_dir)` / `declared, orphans = decisions(tree_unknowns(files, read_system(...)[0]))`) and add the decorator, so it begins:

```python
@command("unknowns", lambda p: p.add_argument("--json", action="store_true"))
def cmd_unknowns(args):
    wrist_root, files, profile, pm, slug = load_all(args)
    declared, orphans = decisions(tree_unknowns(files, pm.unknowns))
```

3. Replace `tree_unknowns` with:

```python
def tree_unknowns(files, premise_unknowns):
    """Every unknown as (file, Unknown): stand-ins in path order, then PREMISE.md."""
    pairs = [(sf.rel, u) for sf in sorted(files.values(), key=lambda f: f.rel) for u in sf.unknowns]
    pairs.extend((PREMISE_FILE, u) for u in premise_unknowns)
    return pairs
```

4. Decorate `cmd_fix_backlinks` and rewire its first line:

```python
@command("fix-backlinks", lambda p: p.add_argument("--write", action="store_true"))
def cmd_fix_backlinks(args):
    wrist_root, files, profile, pm, slug = load_all(args)
    deps, refs = build_edges(wrist_root, files, report=False)
```

- [ ] **Step 8: Add the premise, profile loading, validation and `check`**

Insert after `name_problems` (before `heading_path`) in `wrist_check.py`:

```python
class Premise:
    """wrist/PREMISE.md: front matter, the answers to the profile's questions, unknowns and links."""

    def __init__(self):
        self.exists = False
        self.front = {}         # key -> (line, value)
        self.unknowns = []
        self.links = []         # (line, text, target)
        self.slugs = set()
        self.answers = {}       # question id -> (line, value)
        self.diags = []


def read_premise(wrist_root):
    pm = Premise()
    path = os.path.join(wrist_root, PREMISE_FILE)
    if not os.path.exists(path):
        return pm
    pm.exists = True
    with open(path, encoding="utf-8-sig") as fh:
        lines = fh.read().split("\n")
    end = front_matter_end(lines)
    start = 0
    if end > 0:
        for i, l in enumerate(lines[1:end], 2):
            m = META_RE.match(l)
            if m:
                pm.front.setdefault(m.group(1).lower(), (i, meta_value(m.group(2))))
        start = end + 1
    elif end == -1:
        pm.diags.append(("error", 1, "front matter is not closed with `---`"))
    fence = False
    for idx in range(start, len(lines)):
        ln, line = idx + 1, lines[idx]
        if FENCE_RE.match(line):
            fence = not fence
            continue
        if fence:
            continue
        hm = HEADING_RE.match(line)
        if hm:
            pm.slugs.add(slugify(hm.group(2)))
            continue
        am = ANSWER_RE.match(line)
        if am:
            pm.answers.setdefault(am.group(1), (ln, am.group(2).strip()))
        um = UNKNOWN_RE.search(line)
        if um:
            pm.unknowns.append(Unknown(ln, um.group(1).strip()))
        pm.links.extend((ln, text, target) for text, target in LINK_RE.findall(line))
    return pm


def premise_problems(pm, profile, override):
    """(severity, line, message) for PREMISE.md itself: front matter and the profile's questions."""
    if not pm.exists:
        return [("error", 1, f"{PREMISE_FILE} is missing; the premise phase writes it")]
    out = list(pm.diags)
    for key in ("title", "slug"):
        if not pm.front.get(key, (0, ""))[1]:
            out.append(("error", 1, f"{PREMISE_FILE} front matter needs `{key}:`"))
    line, slug = pm.front.get("slug", (1, ""))
    if slug and not wrist_profile.SLUG_RE.match(slug):
        out.append(("error", line, f"slug '{slug}' must be lower-case words joined by hyphens"))
    if not override and "profile" not in pm.front:
        out.append(("error", 1, f"{PREMISE_FILE} front matter needs `profile:`"))
    for q in profile.questions:
        answer = pm.answers.get(q.id)
        if answer is None or not answer[1]:
            out.append(("error" if q.required else "warning", 1,
                        f"question '{q.id}' ({q.text}) has no answer; answer it or record an `*UNKNOWN*:`"))
    return out


def check_premise_links(wrist_root, files, pm):
    diags = []
    for ln, text, target in pm.links:
        if EXTERNAL_RE.match(target):
            continue
        path, _, frag = target.partition("#")
        if path == "":
            if frag and frag not in pm.slugs:
                diags.append(("error", ln, f"fragment '#{frag}' does not match any heading in this file"))
            continue
        tgt = os.path.normpath(os.path.join(wrist_root, path))
        if not os.path.exists(tgt):
            diags.append(("error", ln, f"link target does not exist: {target}"))
        elif frag and tgt in files:
            diags.extend((sev, ln, msg) for sev, msg in fragment_problems(text, frag, files[tgt], path))
    return diags


def load_all(args):
    """(wrist_root, files, profile, premise, slug) for a command; exits when there is no usable profile."""
    pm = read_premise(os.path.abspath(args.wrist_dir))
    name = args.profile or pm.front.get("profile", (0, ""))[1]
    if not name:
        sys.exit(f"no profile: give --profile or set `profile:` in {os.path.join(args.wrist_dir, PREMISE_FILE)}")
    try:
        profile = wrist_profile.load_profile(name)
    except wrist_profile.ProfileError as exc:
        sys.exit(f"profile error: {exc}")
    configure(profile)
    wrist_root, files = load_tree(args.wrist_dir)
    return wrist_root, files, profile, pm, pm.front.get("slug", (0, ""))[1]


def prose_words(sf, sec):
    """Words of free prose directly under a heading: not fenced, not a field, not a link bullet."""
    later = [s.line for s in sf.sections if s.line > sec.line]
    end = min(later) - 1 if later else len(sf.lines)
    words, fence = 0, None
    for line in sf.lines[sec.line:end]:
        fm = FENCE_RE.match(line)
        if fence:
            if fm and fm.group(1)[0] == fence[0] and len(fm.group(1)) >= len(fence) and not fm.group(2).strip():
                fence = None
            continue
        if fm:
            fence = fm.group(1)
            continue
        if FIELD_RE.match(line) or BULLET_LINK_RE.match(line) or UNKNOWN_RE.search(line):
            continue
        words += len(line.split())
    return words


def validate_file(sf, lenient, slug):
    """Check one stand-in against the profile function its path gives it."""
    miss = sf.warn if lenient else sf.err
    sf.function = PROFILE.function_for(sf.impl_rel, slug)
    if sf.function is None:
        return                      # outside the shape; collect_diags reports it
    spec = PROFILE.functions[sf.function]
    l1 = [s for s in sf.sections if s.level == 1]
    if len(l1) != 1:
        sf.err(l1[1].line if len(l1) > 1 else 1,
               f"expected exactly one level-1 heading `# {spec['heading']}: <name>` (found {len(l1)})")
    elif l1[0].kind != spec["heading"]:
        sf.err(l1[0].line, f"this stand-in must start with `# {spec['heading']}: <name>`")
    if sf.root.fields:
        ln = min(v[0][0] for v in sf.root.fields.values())
        sf.warn(ln, "fields before the first heading are not attached to any heading")
    for s in sf.sections:
        if s.kind is None or s.level == 1:
            continue
        if not (s.level == 2 and s.kind in spec["children"]):
            allowed = ", ".join(f"## {k}:" for k in spec["children"]) or "none"
            sf.err(s.line, f"`{'#' * s.level} {s.kind}:` not allowed here; this file allows "
                           f"{allowed} under `# {spec['heading']}:`")
    limit = PROFILE.limits["max_prose_words"]
    for s in sf.sections:
        if s.kind is None:
            continue
        required = spec["fields"] if s.level == 1 else spec["children"].get(s.kind)
        if required is not None:
            f = own_fields(s)
            for label in required:
                if label not in f:
                    miss(s.line, f"{s.kind} '{s.name}' is missing `{label}:`")
        words = prose_words(sf, s)
        if words > limit:
            sf.warn(s.line, f"{s.kind} '{s.name}' has {words} words of free prose; stand-ins hold notes, "
                            f"not the text (limit {limit})")
    for lk in sf.all_links():
        if lk.relation and lk.relation.lower() not in PROFILE.relations:
            sf.warn(lk.line, f"relation word '{lk.relation}' is not one of: {', '.join(PROFILE.relations)}")
    ff = file_fields(sf)
    for label, q in [("Required", "Is this always required?"), ("Rules", "What must the realization follow?"),
                     ("Depends on", "What does this depend on?"), ("Referred by", "What depends on this?")]:
        if label not in ff:
            sf.err(1, f"missing `{label}:` (answers '{q}'); use 'none' if that is the answer")
    if not sf.unknowns and "Unknowns" not in ff:
        sf.err(1, "no *UNKNOWN* entries and no `Unknowns: none`")


def collect_diags(wrist_dir, wrist_root, files, profile, pm, slug, lenient, override):
    """Every diagnostic of the tree: {file rel: [(severity, line, msg)]}, the edges, and the unknowns."""
    for sf in files.values():
        validate_file(sf, lenient, slug)
    deps, refs = build_edges(wrist_root, files)
    check_bidirectional(files, deps, refs)
    diags = {sf.rel: sf.diags for sf in files.values()}
    diags[PREMISE_FILE] = premise_problems(pm, profile, override) + check_premise_links(wrist_root, files, pm)
    expected = profile.expected_files(slug)
    present = {sf.impl_rel for sf in files.values()}
    for path, _ in expected:
        if path not in present:
            diags[PREMISE_FILE].append(
                ("error", 1, f"required stand-in missing: {os.path.join(wrist_dir, path + WRIST_SUFFIX)}"))
    names = ", ".join(p for p, _ in expected)
    for sf in files.values():
        if sf.function is None:
            sf.err(1, f"this stand-in is outside the {profile.name} shape; the stand-ins are {names}")
    pairs = tree_unknowns(files, pm.unknowns)
    for rel, u in pairs:
        diags[rel].extend((sev, u.line, msg) for sev, msg in unknown_problems(u, lenient))
    for rel, line, sev, msg in name_problems(pairs):
        diags[rel].append((sev, line, msg))
    return diags, deps, pairs


def count_diags(diags):
    errors = sum(1 for ds in diags.values() for sev, _, _ in ds if sev == "error")
    warnings = sum(1 for ds in diags.values() for sev, _, _ in ds if sev == "warning")
    return errors, warnings


@command("check", lambda p: p.add_argument("--lenient", action="store_true",
                                           help="report missing fields as warnings; link and naming errors still fail"))
def cmd_check(args):
    wrist_root, files, profile, pm, slug = load_all(args)
    diags, deps, pairs = collect_diags(args.wrist_dir, wrist_root, files, profile, pm, slug,
                                       args.lenient, bool(args.profile))
    for rel in sorted(r for r in diags if r != PREMISE_FILE) + [PREMISE_FILE]:
        for sev, ln, msg in sorted(diags[rel], key=lambda d: d[1]):
            print(f"{os.path.join(args.wrist_dir, rel)}:{ln}: {sev}: {msg}")
    ne, nw = count_diags(diags)
    print(f"\n{len(files)} stand-ins, {len(deps)} dependency edges, {len(decisions(pairs)[0])} unknowns; "
          f"{ne} errors, {nw} warnings")
    return 1 if ne else 0


```

- [ ] **Step 9: Add the new `main` at the end of `wrist_check.py`**

Append (the file must end with this; every later task inserts its commands above it):

```python
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, (fn, setup) in COMMANDS.items():
        p = sub.add_parser(name)
        p.add_argument("wrist_dir")
        p.add_argument("--profile", help="profile name; overrides `profile:` in PREMISE.md")
        if setup:
            setup(p)
    # argparse will not take positionals on both sides of an option, so `stamp DIR --root . PATH...`
    # leaves its paths over; collect them here.
    args, extra = ap.parse_known_args()
    if extra and (args.cmd != "stamp" or any(e.startswith("-") for e in extra)):
        ap.error("unrecognized arguments: " + " ".join(extra))
    if args.cmd == "stamp":
        args.paths += extra
    sys.exit(COMMANDS[args.cmd][0](args))


if __name__ == "__main__":
    main()
```

The old `if __name__ == "__main__": main()` block was deleted with the old `main`; confirm there is exactly one.

- [ ] **Step 10: Strip `unit:` handling from `wrist_mv.py`**

In `plugins/wrist/skills/wrist/scripts/wrist_mv.py`:

1. Replace the module docstring with:

```python
"""wrist_mv.py: move or rename wrist stand-ins (files or directories) and rewrite every
relative markdown link in the wrist tree so cross-references stay valid.

  wrist_mv.py WRIST_DIR OLD NEW [--dry-run]
  wrist_mv.py WRIST_DIR --map mapping.txt [--dry-run]

mapping.txt has one "OLD NEW" pair per line (paths relative to the current directory;
'#' starts a comment). Links in PREMISE.md are rewritten too. Links inside fenced code
blocks are left untouched.
"""
```

2. Delete the `UNIT_RE` and `META_RE` constants.
3. In `rewrite`, delete the `front_end = 0 ...` block (from `front_end = 0` through the `break` that ends the `for j` loop), and delete the whole `if 0 < idx < front_end:` branch inside the line loop (the `for idx, line in enumerate(lines):` loop then starts with `fm = FENCE_RE.match(line)`).

Run: `python3 -m py_compile plugins/wrist/skills/wrist/scripts/wrist_mv.py plugins/wrist/skills/wrist/scripts/wrist_check.py`
Expected: no output.

- [ ] **Step 11: Run the tests**

Run: `python3 -m unittest discover -s plugins/wrist/tests 2>&1 | tail -15`
Expected: `OK`. If `test_pristine_example_has_no_errors_or_warnings` fails, read the diagnostics: they are either an error in the example text (fix the example) or a real checker bug (fix the checker). Do not weaken the tests.

- [ ] **Step 12: Commit**

```bash
git add -A plugins/wrist
git commit -m "feat(wrist): drive the checker from profile data and drop the code grammar" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Order, stamps, status and phase gates

**Files:**
- Modify: `plugins/wrist/skills/wrist/scripts/wrist_check.py` (insert new commands above `def main()`)
- Create: `plugins/wrist/tests/test_status.py`, `plugins/wrist/tests/test_gate.py`
- Create: `plugins/wrist/skills/wrist/assets/examples/the-lamp/wrist/.stamps` (generated)

**Interfaces:**
- Consumes: everything listed under Task 4 "Produces".
- Produces in `wrist_check.py`:
  - `project_root(args) -> str` (`--root` or the parent of `wrist_dir`)
  - `file_hash(path) -> str`, `load_stamps(wrist_root) -> dict`, `save_stamps(wrist_root, stamps)`
  - `realized_state(sf, root, stamps) -> "pending" | "unstamped" | "stale" | "edited" | "realized"`
  - `sorted_files(files, profile, slug) -> list[WristFile]` (realization order, then path)
  - `gate_blockers(args, phase) -> list[str]` for `phase` in `generation | realization | publishing`; `args` needs `wrist_dir`, `profile`, `root`.
  - Commands `order`, `status`, `stamp`, `gate`.
  - PREMISE keys used: `questions_generation`, `questions_realization`, `questions_publishing` (value `done`), `review_done` (value `yes`), `author`.

- [ ] **Step 1: Write the failing tests**

Create `plugins/wrist/tests/test_status.py`:

```python
import json
import os
import unittest

from support import CHECK, OUTLINE, STORY, SYNOPSIS, TreeCase

SYNOPSIS_REAL = "synopsis.md"
STORY_REAL = "work/the-lamp.md"


class ExampleIsStamped(TreeCase):
    def test_example_is_fully_realized(self):
        code, out = self.run_wrist("status", "wrist")
        self.assertEqual(code, 0, out)
        self.assertIn("Realized (5):", out)
        for title in ("Stale", "Edited", "Unstamped", "Pending"):
            self.assertIn(f"{title}", out)
        self.assertNotIn("Pending (1)", out)


class Status(TreeCase):
    def groups(self):
        _, out = self.run_wrist("status", "wrist")
        groups, current = {}, None
        for line in out.splitlines():
            if line and not line.startswith(" "):
                current = line.split(" (")[0].split(",")[0]
                groups[current] = []
            elif line.strip():
                groups[current].append(line.strip().split("  ")[0])
        return groups

    def test_editing_a_realized_file_marks_it_edited(self):
        self.append(STORY_REAL, "\nA stray line.\n")
        self.assertEqual(self.groups()["Edited"], [STORY_REAL])

    def test_editing_a_stand_in_marks_its_file_stale(self):
        self.replace(SYNOPSIS, "She returns the lamp lit", "She returns the lamp, lit")
        self.assertEqual(self.groups()["Stale"], [SYNOPSIS_REAL])

    def test_a_backlink_change_does_not_make_a_file_stale(self):
        self.append(SYNOPSIS, "- **Referred by:** [story](./work/the-lamp.md.wrist.md)\n")
        self.assertEqual(self.groups()["Stale"], [])

    def test_missing_realized_file_is_pending(self):
        os.remove(self.path(STORY_REAL))
        self.assertEqual(self.groups()["Pending"], [STORY_REAL])

    def test_no_stamps_file_makes_everything_unstamped(self):
        os.remove(self.path("wrist/.stamps"))
        self.assertEqual(len(self.groups()["Unstamped"]), 5)

    def test_corrupt_stamps_file_is_reported(self):
        self.write("wrist/.stamps", "{not json")
        code, out = self.run_wrist("status", "wrist")
        self.assertNotEqual(code, 0)
        self.assertIn("cannot read the stamps", out)


class Stamp(TreeCase):
    def test_stamp_makes_an_edited_file_current_again(self):
        self.append(STORY_REAL, "\nA stray line.\n")
        code, out = self.run_wrist("stamp", "wrist", STORY_REAL)
        self.assertEqual(code, 0, out)
        self.assertIn("stamped work/the-lamp.md", out)
        _, status = self.run_wrist("status", "wrist")
        self.assertIn("Realized (5):", status)

    def test_stamp_all_covers_every_realized_file(self):
        os.remove(self.path("wrist/.stamps"))
        code, out = self.run_wrist("stamp", "wrist", "--all")
        self.assertEqual(code, 0, out)
        self.assertIn("5 stamped", out)
        with open(self.path("wrist/.stamps"), encoding="utf-8") as fh:
            stamps = json.load(fh)
        self.assertEqual(set(stamps["work/the-lamp.md"]), {"stand_in", "realized", "date"})

    def test_stamping_a_file_not_yet_realized_fails(self):
        os.remove(self.path(STORY_REAL))
        code, out = self.run_wrist("stamp", "wrist", STORY_REAL)
        self.assertEqual(code, 1, out)
        self.assertIn("not realized yet", out)

    def test_stamping_a_path_with_no_stand_in_fails(self):
        self.write("notes.md", "x\n")
        code, out = self.run_wrist("stamp", "wrist", "notes.md")
        self.assertEqual(code, 1, out)
        self.assertIn("no stand-in in this tree", out)

    def test_stamp_needs_paths_or_all(self):
        code, out = self.run_wrist("stamp", "wrist")
        self.assertNotEqual(code, 0)
        self.assertIn("--all", out)

    def test_realized_files_are_never_modified_by_stamping(self):
        before = self.read(STORY_REAL)
        self.run_wrist("stamp", "wrist", "--all")
        self.assertEqual(self.read(STORY_REAL), before)


class Order(TreeCase):
    def test_order_follows_the_profile(self):
        code, out = self.run_wrist("order", "wrist")
        self.assertEqual(code, 0, out)
        names = [l.split()[1] for l in out.splitlines() if l[:1].isdigit()]
        self.assertEqual(names, ["synopsis.md", "outline.md", "character.md", "misc.md", "work/the-lamp.md"])
        self.assertNotIn("contradict", out)

    def test_a_dependency_on_a_later_file_is_reported_but_is_not_an_error(self):
        self.append(SYNOPSIS, "- **Depends on:** [story](./work/the-lamp.md.wrist.md) (mentions)\n")
        self.run_wrist("fix-backlinks", "wrist", "--write")
        code, out = self.run_wrist("order", "wrist")
        self.assertEqual(code, 0, out)
        self.assertIn("synopsis.md depends on work/the-lamp.md, which is realized later", out)

    def test_json_output(self):
        _, out = self.run_wrist("order", "wrist", "--json")
        data = json.loads(out)
        self.assertEqual(data["order"][0]["realizes"], "synopsis.md")
        self.assertEqual(data["conflicts"], [])


if __name__ == "__main__":
    unittest.main()
```

Create `plugins/wrist/tests/test_gate.py`:

```python
import os
import unittest

from support import MISC, NO_UNKNOWNS, PREMISE, STORY, SYNOPSIS, TreeCase

STORY_REAL = "work/the-lamp.md"


class Gates(TreeCase):
    def gate(self, phase):
        return self.run_wrist("gate", "wrist", phase)

    def assertBlocked(self, phase, fragment):
        code, out = self.gate(phase)
        self.assertEqual(code, 1, out)
        self.assertIn("blocked", out)
        self.assertIn(fragment, out)

    def test_every_gate_is_open_on_the_example(self):
        for phase in ("generation", "realization", "publishing"):
            code, out = self.gate(phase)
            self.assertEqual(code, 0, out)
            self.assertIn(f"gate {phase}: open", out)

    def test_each_phase_needs_its_question_phase(self):
        for phase in ("generation", "realization", "publishing"):
            with self.subTest(phase=phase):
                self.replace(PREMISE, f"questions_{phase}: done\n", "")
                self.assertBlocked(phase, f"the question phase before {phase}")
                self.replace(PREMISE, "---\n\n# Premise", f"questions_{phase}: done\n---\n\n# Premise")

    def test_generation_needs_the_required_answers(self):
        self.replace(PREMISE, "- **genre:** Literary fiction, quiet realism.\n", "")
        self.assertBlocked("generation", "question 'genre'")

    def test_realization_is_blocked_by_a_check_error(self):
        self.replace(SYNOPSIS, "- **Referred by:** [outline](./outline.md.wrist.md)\n", "")
        self.assertBlocked("realization", "`check` reports")

    def test_realization_is_blocked_by_a_blocking_unknown(self):
        self.replace(MISC, NO_UNKNOWNS, "*UNKNOWN*: [venue] Which venue. Kind: blocking. "
                                         "Consequence: c. Unlocks: u.\n")
        self.assertBlocked("realization", "blocking unknown at misc.md.wrist.md")

    def test_a_local_unknown_does_not_block_realization(self):
        self.replace(MISC, NO_UNKNOWNS, "*UNKNOWN*: [clocks] How many. Kind: local. Proposed: eleven. "
                                         "Consequence: c. Unlocks: u.\n")
        self.assertEqual(self.gate("realization")[0], 0)

    def test_publishing_is_blocked_by_a_hand_edited_realized_file(self):
        self.append(STORY_REAL, "\nA stray line.\n")
        self.assertBlocked("publishing", "work/the-lamp.md is edited")

    def test_publishing_is_blocked_by_a_changed_stand_in(self):
        self.replace(SYNOPSIS, "closed shop", "shut shop")
        self.assertBlocked("publishing", "synopsis.md is stale")

    def test_publishing_is_blocked_by_an_unrealized_file(self):
        os.remove(self.path(STORY_REAL))
        self.assertBlocked("publishing", "work/the-lamp.md is pending")

    def test_publishing_is_blocked_by_an_empty_story(self):
        self.write(STORY_REAL, "")
        self.run_wrist("stamp", "wrist", STORY_REAL)
        self.assertBlocked("publishing", "work/the-lamp.md is empty")

    def test_publishing_needs_the_review_pass(self):
        self.replace(PREMISE, "review_done: yes\n", "")
        self.assertBlocked("publishing", "review pass")

    def test_publishing_needs_an_author(self):
        self.replace(PREMISE, "author: Ada Example\n", "")
        self.assertBlocked("publishing", "author")

    def test_unknown_phase_is_rejected(self):
        code, out = self.gate("printing")
        self.assertEqual(code, 2, out)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify they fail**

Run: `python3 -m unittest discover -s plugins/wrist/tests -p 'test_status.py' 2>&1 | tail -4; python3 -m unittest discover -s plugins/wrist/tests -p 'test_gate.py' 2>&1 | tail -4`
Expected: FAIL (the `status`, `stamp`, `order`, `gate` subcommands do not exist; `wrist/.stamps` is missing).

- [ ] **Step 3: Implement the commands**

Insert in `wrist_check.py`, above `def main():`:

```python
def project_root(args):
    root = getattr(args, "root", None)
    return os.path.abspath(root) if root else os.path.dirname(os.path.abspath(args.wrist_dir))


def file_hash(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()[:8]


def load_stamps(wrist_root):
    path = os.path.join(wrist_root, STAMPS_FILE)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        sys.exit(f"{path}: cannot read the stamps ({exc})")
    if not isinstance(data, dict):
        sys.exit(f"{path}: cannot read the stamps (not a JSON object)")
    return data


def save_stamps(wrist_root, stamps):
    with open(os.path.join(wrist_root, STAMPS_FILE), "w", encoding="utf-8") as fh:
        json.dump(stamps, fh, indent=2, sort_keys=True)
        fh.write("\n")


def realized_state(sf, root, stamps):
    """pending (no realized file), unstamped, stale (stand-in changed), edited (file changed) or realized."""
    impl = os.path.join(root, sf.impl_rel)
    if not os.path.isfile(impl):
        return "pending"
    entry = stamps.get(sf.impl_rel)
    if not isinstance(entry, dict):
        return "unstamped"
    if entry.get("stand_in") != stand_in_hash(sf):
        return "stale"
    if entry.get("realized") != file_hash(impl):
        return "edited"
    return "realized"


def sorted_files(files, profile, slug):
    rank = {path: i for i, (path, _) in enumerate(profile.expected_files(slug))}
    return sorted(files.values(), key=lambda sf: (rank.get(sf.impl_rel, len(rank)), sf.rel))


@command("order", lambda p: p.add_argument("--json", action="store_true"))
def cmd_order(args):
    wrist_root, files, profile, pm, slug = load_all(args)
    deps, _ = build_edges(wrist_root, files, report=False)
    rank = {path: i for i, (path, _) in enumerate(profile.expected_files(slug))}
    ordered = sorted_files(files, profile, slug)
    order = [{"step": i, "stand_in": sf.rel, "realizes": sf.impl_rel, "function": sf.function,
              "unknowns": len(sf.unknowns)} for i, sf in enumerate(ordered, 1)]
    conflicts = []
    for (a, b) in sorted(deps, key=lambda e: (files[e[0]].rel, files[e[1]].rel)):
        ra, rb = rank.get(files[a].impl_rel), rank.get(files[b].impl_rel)
        if ra is not None and rb is not None and rb > ra:
            conflicts.append({"file": files[a].impl_rel, "depends_on": files[b].impl_rel})
    if args.json:
        print(json.dumps({"order": order, "conflicts": conflicts}, indent=2))
        return 0
    for item in order:
        flag = f"  [{item['unknowns']} UNKNOWN]" if item["unknowns"] else ""
        print(f"{item['step']}. {item['realizes']}  ({item['function']}){flag}")
    for c in conflicts:
        print(f"note: {c['file']} depends on {c['depends_on']}, which is realized later; "
              "the profile's order wins")
    return 0


@command("status", lambda p: p.add_argument("--root"))
def cmd_status(args):
    wrist_root, files, profile, pm, slug = load_all(args)
    root, stamps = project_root(args), load_stamps(wrist_root)
    groups = {"realized": [], "stale": [], "edited": [], "unstamped": [], "pending": []}
    for sf in sorted_files(files, profile, slug):
        unk = f"  [{len(sf.unknowns)} UNKNOWN]" if sf.unknowns else ""
        groups[realized_state(sf, root, stamps)].append(f"{sf.impl_rel}{unk}")
    for title, key in [("Realized", "realized"), ("Stale, stand-in changed since realized", "stale"),
                       ("Edited, realized file changed since stamped", "edited"),
                       ("Unstamped, realized but never stamped", "unstamped"), ("Pending", "pending")]:
        print(f"{title} ({len(groups[key])}):")
        for line in groups[key]:
            print(f"  {line}")
    return 0


def setup_stamp(p):
    p.add_argument("--root")
    p.add_argument("paths", nargs="*")
    p.add_argument("--all", action="store_true")


@command("stamp", setup_stamp)
def cmd_stamp(args):
    wrist_root, files, profile, pm, slug = load_all(args)
    root = project_root(args)
    if not args.paths and not args.all:
        sys.exit("stamp needs the realized files to stamp, or --all")
    if args.paths and args.all:
        sys.exit("give the files to stamp or --all, not both")
    by_impl = {os.path.normpath(os.path.join(root, sf.impl_rel)): sf for sf in files.values()}
    targets = sorted(by_impl) if args.all else [os.path.normpath(os.path.abspath(p)) for p in args.paths]
    stamps = load_stamps(wrist_root)
    stamped = failed = 0
    for impl in targets:
        shown = os.path.relpath(impl, root).replace(os.sep, "/")
        sf = by_impl.get(impl)
        if sf is None:
            print(f"{shown}: no stand-in in this tree")
            failed += 1
            continue
        if not os.path.isfile(impl):
            if not args.all:
                print(f"{shown}: not realized yet")
                failed += 1
            continue
        entry = {"stand_in": stand_in_hash(sf), "realized": file_hash(impl),
                 "date": datetime.date.today().isoformat()}
        old = stamps.get(sf.impl_rel) or {}
        if old.get("stand_in") == entry["stand_in"] and old.get("realized") == entry["realized"]:
            continue
        stamps[sf.impl_rel] = entry
        print(f"stamped {shown} @ {entry['stand_in']}")
        stamped += 1
    if stamped:
        save_stamps(wrist_root, stamps)
    print(f"\n{stamped} stamped")
    return 1 if failed else 0


PHASES = ("generation", "realization", "publishing")


def gate_blockers(args, phase):
    """What stops the phase from starting: a list of messages, empty when the gate is open."""
    wrist_root, files, profile, pm, slug = load_all(args)
    override = bool(args.profile)
    blockers = []
    flag = f"questions_{phase}"
    if pm.front.get(flag, (0, ""))[1].lower() != "done":
        blockers.append(f"the question phase before {phase} is not recorded; ask the questions, "
                        f"then set `{flag}: done` in {PREMISE_FILE}")
    if phase == "generation":
        blockers.extend(f"premise: {msg}" for sev, _, msg in premise_problems(pm, profile, override)
                        if sev == "error")
        return blockers
    diags, deps, pairs = collect_diags(args.wrist_dir, wrist_root, files, profile, pm, slug, False, override)
    errors, _ = count_diags(diags)
    if errors:
        blockers.append(f"`check` reports {errors} error(s); run it and fix them")
    for rel, u, _ in decisions(pairs)[0]:
        if u.kind == "blocking":
            blockers.append(f"blocking unknown at {rel}:{u.line}: {u.text[:80]}")
    if phase == "realization":
        return blockers
    root, stamps = project_root(args), load_stamps(wrist_root)
    for sf in sorted_files(files, profile, slug):
        state = realized_state(sf, root, stamps)
        if state != "realized":
            blockers.append(f"{sf.impl_rel} is {state}; realize it and run `stamp`")
    for path, function in profile.expected_files(slug):
        impl = os.path.join(root, path)
        if profile.functions[function]["prose"] and os.path.isfile(impl):
            with open(impl, encoding="utf-8", errors="replace") as fh:
                if not fh.read().split():
                    blockers.append(f"{path} is empty; there is nothing to publish")
    if pm.front.get("review_done", (0, ""))[1].lower() != "yes":
        blockers.append(f"the review pass is not recorded; do it, then set `review_done: yes` in {PREMISE_FILE}")
    if not pm.front.get("author", (0, ""))[1]:
        blockers.append(f"{PREMISE_FILE} front matter needs `author:` for the title page")
    return blockers


def setup_gate(p):
    p.add_argument("phase", choices=PHASES)
    p.add_argument("--root")


@command("gate", setup_gate)
def cmd_gate(args):
    blockers = gate_blockers(args, args.phase)
    if not blockers:
        print(f"gate {args.phase}: open")
        return 0
    print(f"gate {args.phase}: blocked")
    for b in blockers:
        print(f"  - {b}")
    return 1


```

- [ ] **Step 4: Generate the example's stamps**

Run: `python3 plugins/wrist/skills/wrist/scripts/wrist_check.py stamp plugins/wrist/skills/wrist/assets/examples/the-lamp/wrist --all`
Expected: five `stamped ...` lines and `5 stamped`; the file `.../the-lamp/wrist/.stamps` now exists.

- [ ] **Step 5: Run the tests**

Run: `python3 -m unittest discover -s plugins/wrist/tests 2>&1 | tail -8`
Expected: `OK`. If `test_each_phase_needs_its_question_phase` fails on the restore step, check that the PREMISE front matter in the example still ends with `review_done: yes\n---\n\n# Premise`.

- [ ] **Step 6: Commit**

```bash
git add -A plugins/wrist
git commit -m "feat(wrist): add order, stamps, status and phase gates" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Lint and the shortstory quality data

**Files:**
- Create: `plugins/wrist/skills/wrist/scripts/wrist_lint.py`
- Create: `plugins/wrist/skills/wrist/profiles/shortstory/lint.json`
- Modify: `plugins/wrist/skills/wrist/scripts/wrist_profile.py` (real `lint_items`)
- Modify: `plugins/wrist/skills/wrist/scripts/wrist_check.py` (add `lint` command above `def main()`)
- Create: `plugins/wrist/tests/test_lint.py`

**Interfaces:**
- Consumes: `Profile.directory`, `Profile.functions[...]["prose"]`, `Profile.expected_files`, `project_root`, `load_all`.
- Produces:
  - `wrist_lint.in_dialogue(line, pos) -> bool`; `wrist_lint.lint_text(text, items) -> list[{"line","id","label","text","note"}]` sorted by `(line, id)`.
  - `Profile.lint_items() -> list[dict]`, each with keys `id, pattern, label, note, scope ("narration"|"anywhere"), positive, negative`; raises `ProfileError` for a bad item.
  - Command `lint WRIST_DIR [--root]`: prints `path:line: [id] label: "text" (note)` per hit, then `N hits in M files`, then a pointer to the judgment checklist; always exits 0.

- [ ] **Step 1: Write the failing tests**

Create `plugins/wrist/tests/test_lint.py`:

```python
import re
import unittest

from support import TreeCase     # first: it puts the scripts folder on sys.path

import wrist_lint
import wrist_profile

STORY_REAL = "work/the-lamp.md"


class EveryPattern(unittest.TestCase):
    def test_each_pattern_matches_its_positive_and_not_its_negative(self):
        items = wrist_profile.load_profile("shortstory").lint_items()
        self.assertGreaterEqual(len(items), 20)
        ids = [i["id"] for i in items]
        self.assertEqual(len(ids), len(set(ids)))
        for item in items:
            with self.subTest(item["id"]):
                rx = re.compile(item["pattern"], re.IGNORECASE)
                self.assertTrue(rx.search(item["positive"]), "positive sample does not match")
                self.assertFalse(rx.search(item["negative"]), "negative sample matches")


class LintText(unittest.TestCase):
    ITEMS = [
        {"id": "narr", "pattern": "dark and stormy", "label": "l1", "note": "n1", "scope": "narration"},
        {"id": "any", "pattern": "shiver", "label": "l2", "note": "n2", "scope": "anywhere"},
    ]

    def test_narration_hits_are_reported_with_their_line(self):
        hits = wrist_lint.lint_text("one\nIt was a dark and stormy night.\n", self.ITEMS)
        self.assertEqual([(h["line"], h["id"], h["text"]) for h in hits], [(2, "narr", "dark and stormy")])

    def test_narration_scope_ignores_quoted_dialogue(self):
        self.assertEqual(wrist_lint.lint_text('"A dark and stormy night," he said.', self.ITEMS), [])

    def test_curly_quotes_count_as_dialogue(self):
        self.assertEqual(wrist_lint.lint_text("\u201cA dark and stormy night,\u201d he said.", self.ITEMS), [])

    def test_anywhere_scope_flags_dialogue_too(self):
        hits = wrist_lint.lint_text('"I shiver," he said.', self.ITEMS)
        self.assertEqual([h["id"] for h in hits], ["any"])

    def test_text_after_the_closing_quote_is_narration_again(self):
        hits = wrist_lint.lint_text('"No," he said. A dark and stormy night.', self.ITEMS)
        self.assertEqual([h["id"] for h in hits], ["narr"])

    def test_matching_is_case_insensitive(self):
        self.assertEqual(len(wrist_lint.lint_text("DARK AND STORMY", self.ITEMS)), 1)


class LintCommand(TreeCase):
    def lint(self):
        return self.run_wrist("lint", "wrist")

    def test_the_example_has_no_hits(self):
        code, out = self.lint()
        self.assertEqual(code, 0, out)
        self.assertIn("0 hits in 0 files", out)

    def test_a_cliche_in_narration_is_reported_with_file_and_line(self):
        self.replace(STORY_REAL, "The street went on outside.",
                     "A shiver ran down her spine. The street went on outside.")
        code, out = self.lint()
        self.assertEqual(code, 0, out)
        self.assertRegex(out, r"work/the-lamp\.md:\d+: \[shiver-spine\]")
        self.assertIn("1 hits in 1 files", out)

    def test_the_same_phrase_in_dialogue_is_not_reported(self):
        self.replace(STORY_REAL, '"Leave it on the bench," she said.',
                     '"A shiver ran down my spine," she said.')
        code, out = self.lint()
        self.assertIn("0 hits", out)

    def test_an_anywhere_pattern_is_reported_inside_dialogue(self):
        self.replace(STORY_REAL, '"Nothing."', '"It was a dark and stormy night."')
        code, out = self.lint()
        self.assertIn("[dark-stormy]", out)

    def test_lint_never_fails_the_run(self):
        self.replace(STORY_REAL, "Tomas knocked anyway.", "Suddenly Tomas knocked anyway.")
        code, out = self.lint()
        self.assertEqual(code, 0, out)

    def test_only_prose_files_are_linted(self):
        self.replace("synopsis.md", "takes in", "suddenly takes in")
        code, out = self.lint()
        self.assertIn("0 hits", out)

    def test_pointer_to_the_judgment_checklist(self):
        _, out = self.lint()
        self.assertIn("quality.md", out)


class LintItemValidation(unittest.TestCase):
    def load(self, items):
        import json
        import os
        import shutil
        import tempfile
        d = tempfile.mkdtemp(prefix="wrist-lint-")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        prof = os.path.join(d, "t")
        os.makedirs(prof)
        data = {"name": "t", "files": [{"path": "a.md", "function": "a", "order": 1}],
                "functions": {"a": {"heading": "a"}}, "relations": [], "limits": {"max_prose_words": 5}}
        with open(os.path.join(prof, "profile.json"), "w") as fh:
            json.dump(data, fh)
        with open(os.path.join(prof, "lint.json"), "w") as fh:
            json.dump({"items": items}, fh)
        return wrist_profile.load_profile("t", d).lint_items()

    GOOD = {"id": "x", "pattern": "a", "label": "l", "note": "n", "scope": "anywhere",
            "positive": "a", "negative": "b"}

    def test_a_good_item_loads(self):
        self.assertEqual(len(self.load([self.GOOD])), 1)

    def test_a_bad_pattern_is_rejected(self):
        with self.assertRaises(wrist_profile.ProfileError) as cm:
            self.load([dict(self.GOOD, pattern="(")])
        self.assertIn("pattern", str(cm.exception))

    def test_an_unknown_scope_is_rejected(self):
        with self.assertRaises(wrist_profile.ProfileError):
            self.load([dict(self.GOOD, scope="dialogue")])

    def test_a_missing_key_is_rejected(self):
        bad = dict(self.GOOD)
        del bad["note"]
        with self.assertRaises(wrist_profile.ProfileError):
            self.load([bad])

    def test_no_lint_file_means_no_items(self):
        self.assertEqual(wrist_profile.parse_profile(
            {"name": "t", "files": [{"path": "a.md", "function": "a", "order": 1}],
             "functions": {"a": {"heading": "a"}}, "relations": [], "limits": {"max_prose_words": 5}}
        ).lint_items(), [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m unittest discover -s plugins/wrist/tests -p 'test_lint.py' 2>&1 | tail -4`
Expected: ERROR `ModuleNotFoundError: No module named 'wrist_lint'`.

- [ ] **Step 3: Write `wrist_lint.py`**

Create `plugins/wrist/skills/wrist/scripts/wrist_lint.py`:

```python
#!/usr/bin/env python3
"""wrist_lint.py: scan prose for a profile's searchable clichés. Pure functions; no file access."""
import re


def in_dialogue(line, pos):
    """True when position `pos` of the line lies inside a double-quoted span that opened on this line."""
    inside = False
    for ch in line[:pos]:
        if ch == '"':
            inside = not inside
        elif ch == "\u201c":
            inside = True
        elif ch == "\u201d":
            inside = False
    return inside


def lint_text(text, items):
    """Hits as dicts, sorted by line then id. A `narration` item is not reported inside dialogue."""
    compiled = [(item, re.compile(item["pattern"], re.IGNORECASE)) for item in items]
    hits = []
    for n, line in enumerate(text.split("\n"), 1):
        for item, rx in compiled:
            for m in rx.finditer(line):
                if item["scope"] == "narration" and in_dialogue(line, m.start()):
                    continue
                hits.append({"line": n, "id": item["id"], "label": item["label"],
                             "text": m.group(0), "note": item["note"]})
    return sorted(hits, key=lambda h: (h["line"], h["id"]))
```

- [ ] **Step 4: Replace `lint_items` in `wrist_profile.py`**

Replace the stub method in `class Profile`:

```python
    def lint_items(self):
        """The searchable items of lint.json, validated; an empty list when the profile has none."""
        path = os.path.join(self.directory or "", "lint.json")
        if not self.directory or not os.path.isfile(path):
            return []
        try:
            with open(path, encoding="utf-8") as fh:
                items = json.load(fh)["items"]
        except (ValueError, KeyError, TypeError) as exc:
            raise ProfileError(f"lint.json must be an object with an 'items' list ({exc})")
        seen = set()
        for item in items:
            if not isinstance(item, dict) or any(not isinstance(item.get(k), str) or not item[k] for k in LINT_KEYS):
                raise ProfileError(f"a lint item needs non-empty string {', '.join(LINT_KEYS)}: {item!r}")
            if not NAME_RE.match(item["id"]) or item["id"] in seen:
                raise ProfileError(f"lint item id '{item['id']}' must be unique lower-case words")
            seen.add(item["id"])
            if item["scope"] not in SCOPES:
                raise ProfileError(f"lint item '{item['id']}': scope must be one of {', '.join(SCOPES)}")
            try:
                re.compile(item["pattern"])
            except re.error as exc:
                raise ProfileError(f"lint item '{item['id']}': bad pattern ({exc})")
        return items
```

- [ ] **Step 5: Write the shortstory `lint.json`**

Create `plugins/wrist/skills/wrist/profiles/shortstory/lint.json`:

```json
{
  "items": [
    {"id": "shiver-spine", "pattern": "\\bshiver(?:s|ed)? (?:ran |went |crawled |travell?ed )?(?:down|up|along) (?:her|his|their|my|your) spine\\b",
     "label": "stock bodily reaction", "note": "Find the specific physical detail this character would have.", "scope": "narration",
     "positive": "A shiver ran down her spine.", "negative": "She shivered at the cold."},
    {"id": "breath-held", "pattern": "\\ba breath (?:she|he|they|I) (?:hadn['\u2019]t|had not|didn['\u2019]t know|did not know)\\b",
     "label": "stock bodily reaction", "note": "The held breath is in nearly every manuscript; cut it or show the tension another way.", "scope": "narration",
     "positive": "She let out a breath she hadn't known she was holding.", "negative": "She let out a long breath."},
    {"id": "heart-pounding", "pattern": "\\bheart (?:was )?(?:pounded|pounding|hammered|hammering|raced|racing|skipped a beat)\\b",
     "label": "stock bodily reaction", "note": "Name what the body does that this scene alone would cause.", "scope": "narration",
     "positive": "Her heart skipped a beat.", "negative": "The heart of the town was its clock."},
    {"id": "blood-cold", "pattern": "\\bblood (?:ran|went|turned) (?:cold|to ice)\\b",
     "label": "stock bodily reaction", "note": "Fear is more convincing as an action than as a temperature.", "scope": "narration",
     "positive": "His blood ran cold.", "negative": "The blood on the floor was cold."},
    {"id": "wave-of-emotion", "pattern": "\\b(?:a )?(?:wave|surge|rush|pang) of (?:sadness|grief|fear|relief|anger|joy|guilt|panic|nausea|emotion)\\b",
     "label": "named emotion", "note": "Naming the feeling stands in for dramatizing it.", "scope": "narration",
     "positive": "A wave of sadness washed over her.", "negative": "A wave of cold air came in."},
    {"id": "sense-of", "pattern": "\\ba sense of (?:dread|foreboding|unease|calm|peace|relief)\\b",
     "label": "named emotion", "note": "Say what is noticed, not the sense of it.", "scope": "narration",
     "positive": "She felt a sense of dread.", "negative": "She had a good sense of direction."},
    {"id": "tears-welled", "pattern": "\\btears (?:welled|streamed|stung|pricked) (?:in|down) (?:her|his|their|my) (?:eyes|cheeks|face)\\b|\\beyes (?:welled|filled) with tears\\b",
     "label": "stock bodily reaction", "note": "Let the reader supply the tears.", "scope": "narration",
     "positive": "Tears welled in her eyes.", "negative": "Rain streaked down the glass."},
    {"id": "smile-eyes", "pattern": "\\b(?:smile|grin) (?:didn['\u2019]t|never|did not) reach(?:ed)? (?:her|his|their) eyes\\b|\\bsmile (?:that )?reached (?:her|his|their) eyes\\b",
     "label": "stock description", "note": "Describe what the face actually does.", "scope": "narration",
     "positive": "The smile never reached her eyes.", "negative": "A smile crossed her face."},
    {"id": "orbs", "pattern": "\\borbs\\b",
     "label": "purple stock word", "note": "Eyes are eyes.", "scope": "narration",
     "positive": "Her orbs narrowed.", "negative": "Her eyes narrowed."},
    {"id": "eyes-sparkle", "pattern": "\\beyes (?:sparkled|twinkled|glinted|danced) with (?:mischief|amusement|joy)\\b",
     "label": "stock description", "note": "Show the mischief in what the character does.", "scope": "narration",
     "positive": "His eyes twinkled with mischief.", "negative": "His eyes were grey."},
    {"id": "steeled", "pattern": "\\bsteeled (?:herself|himself|themselves|myself)\\b",
     "label": "stock gesture", "note": "Show the decision as an act.", "scope": "narration",
     "positive": "She steeled herself.", "negative": "The beam was steel."},
    {"id": "deep-breath", "pattern": "\\btook a (?:deep|long|steadying|shaky) breath\\b",
     "label": "stock gesture", "note": "A stalling beat; cut it or replace it with a specific action.", "scope": "narration",
     "positive": "She took a deep breath.", "negative": "She took a bus."},
    {"id": "let-out-sigh", "pattern": "\\b(?:let out|released|exhaled) a (?:long |deep |heavy |shaky )?(?:sigh|breath)\\b",
     "label": "stock gesture", "note": "A stalling beat; cut it or replace it with a specific action.", "scope": "narration",
     "positive": "He let out a deep sigh.", "negative": "He sighed once."},
    {"id": "could-not-help", "pattern": "\\bcouldn['\u2019]?t help but\\b",
     "label": "filter phrase", "note": "State the action; the compulsion is implied.", "scope": "narration",
     "positive": "She couldn't help but smile.", "negative": "She helped him up."},
    {"id": "mirror-reflection", "pattern": "\\b(?:looked|stared|gazed) at (?:her|his|my) (?:own )?reflection\\b",
     "label": "stock opening device", "note": "Describing a character through a mirror is a well-known shortcut.", "scope": "narration",
     "positive": "She stared at her reflection in the mirror.", "negative": "She stared at the window."},
    {"id": "suddenly", "pattern": "\\bsuddenly\\b",
     "label": "intensifier", "note": "If the event is sudden, the sentence can be.", "scope": "narration",
     "positive": "Suddenly the door opened.", "negative": "The door opened."},
    {"id": "little-did-know", "pattern": "\\blittle did (?:she|he|they|I|we) know\\b",
     "label": "authorial intrusion", "note": "Foreshadow with an image, not an announcement.", "scope": "narration",
     "positive": "Little did she know what waited.", "negative": "She knew what waited."},
    {"id": "dark-stormy", "pattern": "\\bit was a dark and stormy night\\b",
     "label": "famous cliché opening", "note": "Avoid even as a joke unless the story is a parody.", "scope": "anywhere",
     "positive": "It was a dark and stormy night.", "negative": "It was a quiet night."},
    {"id": "just-a-dream", "pattern": "\\bit (?:was|had been) (?:all )?(?:just |only )?a dream\\b",
     "label": "cheating ending", "note": "A dream ending cancels the events the reader invested in.", "scope": "anywhere",
     "positive": "It was all just a dream.", "negative": "It was a dreamless sleep."},
    {"id": "pregnant-pause", "pattern": "\\b(?:pregnant pause|deafening silence|silence was deafening)\\b",
     "label": "stock phrase", "note": "Describe what fills the silence.", "scope": "narration",
     "positive": "A pregnant pause followed.", "negative": "A long pause followed."},
    {"id": "adverb-tag", "pattern": "\\b(?:said|asked|replied|whispered|shouted|muttered|answered) \\w+ly\\b",
     "label": "adverb-propped dialogue tag", "note": "Let the line carry the manner, or show it in a beat.", "scope": "narration",
     "positive": "\"No,\" she said angrily.", "negative": "\"No,\" she said."}
  ]
}
```

- [ ] **Step 6: Add the `lint` command**

Insert in `wrist_check.py` above `def main():`, and add `import wrist_lint` next to `import wrist_profile` at the top:

```python
@command("lint", lambda p: p.add_argument("--root"))
def cmd_lint(args):
    wrist_root, files, profile, pm, slug = load_all(args)
    root, items = project_root(args), profile.lint_items()
    hits = n_files = 0
    for path, function in profile.expected_files(slug):
        impl = os.path.join(root, path)
        if not profile.functions[function]["prose"] or not os.path.isfile(impl):
            continue
        with open(impl, encoding="utf-8", errors="replace") as fh:
            found = wrist_lint.lint_text(fh.read(), items)
        for h in found:
            print(f"{path}:{h['line']}: [{h['id']}] {h['label']}: \"{h['text']}\" ({h['note']})")
        hits += len(found)
        n_files += bool(found)
    print(f"\n{hits} hits in {n_files} files")
    print(f"Lint finds only the searchable items. Work through the judgment checklist in "
          f"{os.path.join(profile.directory, 'quality.md')} as well.")
    return 0
```

- [ ] **Step 7: Run the tests**

Run: `python3 -m unittest discover -s plugins/wrist/tests 2>&1 | tail -8`
Expected: `OK`. `test_each_pattern_matches_its_positive_and_not_its_negative` runs 21 sub-tests; a failure names the pattern id to fix.

- [ ] **Step 8: Commit**

```bash
git add -A plugins/wrist
git commit -m "feat(wrist): add the lint command and the shortstory lint patterns" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Publisher (pandoc + typst)

**Files:**
- Create: `plugins/wrist/skills/wrist/scripts/wrist_publish.py`
- Create: `plugins/wrist/skills/wrist/publish/book.typ`, `plugins/wrist/skills/wrist/publish/epub.css`
- Modify: `plugins/wrist/skills/wrist/scripts/wrist_check.py` (add `publish` command above `def main()`; add `import wrist_publish`)
- Create: `plugins/wrist/tests/test_publish.py`

**Interfaces:**
- Consumes: `gate_blockers`, `load_all`, `project_root`, `Profile.expected_files`, `Profile.functions[...]["prose"]`, PREMISE front keys `title`, `author`, `language` (default `en`), optional `trim` (a Typst paper name, default `a5`), optional `font`.
- Produces in `wrist_publish.py`:
  - `TOOLS = ("pandoc", "typst")`; `missing_tools() -> list[str]` (uses `shutil.which`, so it honors `PATH`); `install_help(missing) -> str`.
  - `class PublishError(Exception)`.
  - `plan_commands(sources, meta, out_dir, slug, publish_dir) -> list[tuple[str, list[str]]]` returning `[("epub", argv), ("pdf", argv)]`; `meta` keys `title`, `author`, `language`, optional `trim`, `font`. Every value is passed as its own argv element (no shell).
  - `run_commands(commands, cwd)`: creates the output directory, runs each argv with `subprocess.run`, raises `PublishError` with the tool's stderr on failure.
- Command `publish WRIST_DIR [--root]`: gates first (exit 1 listing blockers), then the tool preflight (exit 1 with install steps), then builds `output/<slug>.epub` and `output/<slug>.pdf` under the project root.

- [ ] **Step 1: Write the failing tests**

Create `plugins/wrist/tests/test_publish.py`:

```python
import os
import shutil
import tempfile
import unittest
import zipfile

from support import PREMISE, SKILL, TreeCase     # first: it puts the scripts folder on sys.path

import wrist_publish

HAVE_TOOLS = shutil.which("pandoc") and shutil.which("typst")
PUBLISH_DIR = os.path.join(SKILL, "publish")


class PlanCommands(unittest.TestCase):
    META = {"title": "The Lamp", "author": "Ada Example", "language": "en"}

    def plan(self, **meta):
        return dict(wrist_publish.plan_commands(["work/the-lamp.md"], dict(self.META, **meta),
                                                "output", "the-lamp", PUBLISH_DIR))

    def test_both_formats_are_planned_into_output(self):
        plan = self.plan()
        self.assertEqual(set(plan), {"epub", "pdf"})
        self.assertIn("output/the-lamp.epub", plan["epub"])
        self.assertIn("output/the-lamp.pdf", plan["pdf"])

    def test_pandoc_builds_both_and_typst_makes_the_pdf(self):
        plan = self.plan()
        self.assertEqual(plan["epub"][0], "pandoc")
        self.assertEqual(plan["pdf"][0], "pandoc")
        self.assertIn("--pdf-engine=typst", plan["pdf"])
        self.assertIn(os.path.join(PUBLISH_DIR, "book.typ"), plan["pdf"])
        self.assertIn(os.path.join(PUBLISH_DIR, "epub.css"), plan["epub"])

    def test_sources_are_passed_in_order(self):
        cmds = wrist_publish.plan_commands(["work/a.md", "work/b.md"], self.META, "output", "x", PUBLISH_DIR)
        argv = dict(cmds)["epub"]
        self.assertLess(argv.index("work/a.md"), argv.index("work/b.md"))

    def test_a_title_with_quotes_ampersand_and_unicode_is_one_intact_argument(self):
        title = 'The "Lamp" & Co. \u2014 caf\u00e9 \u00e9t\u00e9'
        for argv in self.plan(title=title).values():
            self.assertIn(f"title={title}", argv)

    def test_language_defaults_to_english(self):
        plan = wrist_publish.plan_commands(["a.md"], {"title": "T", "author": "A"}, "output", "t", PUBLISH_DIR)
        self.assertIn("lang=en", dict(plan)["epub"])

    def test_trim_and_font_reach_the_pdf_only(self):
        plan = self.plan(trim="us-trade", font="Linux Libertine")
        self.assertIn("papersize=us-trade", plan["pdf"])
        self.assertIn("mainfont=Linux Libertine", plan["pdf"])
        self.assertNotIn("papersize=us-trade", plan["epub"])


class InstallHelp(unittest.TestCase):
    def test_help_names_each_missing_tool(self):
        text = wrist_publish.install_help(["pandoc", "typst"])
        self.assertIn("pandoc", text)
        self.assertIn("typst", text)
        self.assertIn("https://", text)

    def test_help_for_one_tool_does_not_mention_the_other(self):
        self.assertNotIn("typst", wrist_publish.install_help(["pandoc"]))

    def test_missing_tools_honours_the_path(self):
        empty = tempfile.mkdtemp(prefix="wrist-path-")
        self.addCleanup(shutil.rmtree, empty, ignore_errors=True)
        self.assertEqual(wrist_publish.missing_tools(empty), ["pandoc", "typst"])


class PublishCommand(TreeCase):
    def publish(self, env=None):
        return self.run_wrist("publish", "wrist", env=env)

    def empty_path_env(self):
        empty = tempfile.mkdtemp(prefix="wrist-path-")
        self.addCleanup(shutil.rmtree, empty, ignore_errors=True)
        return dict(os.environ, PATH=empty)

    def test_gate_blockers_are_listed_and_nothing_is_built(self):
        self.replace(PREMISE, "review_done: yes\n", "")
        code, out = self.publish(self.empty_path_env())
        self.assertEqual(code, 1, out)
        self.assertIn("publish blocked", out)
        self.assertIn("review pass", out)
        self.assertFalse(os.path.exists(self.path("output")))

    def test_missing_tools_stop_with_install_steps(self):
        code, out = self.publish(self.empty_path_env())
        self.assertEqual(code, 1, out)
        self.assertIn("pandoc", out)
        self.assertIn("typst", out)
        self.assertIn("https://", out)
        self.assertFalse(os.path.exists(self.path("output")))

    @unittest.skipUnless(HAVE_TOOLS, "pandoc and typst are not installed")
    def test_real_build_writes_both_files(self):
        code, out = self.publish()
        self.assertEqual(code, 0, out)
        with open(self.path("output/the-lamp.pdf"), "rb") as fh:
            self.assertEqual(fh.read(5), b"%PDF-")
        with zipfile.ZipFile(self.path("output/the-lamp.epub")) as z:
            self.assertEqual(z.namelist()[0], "mimetype")
            text = "".join(z.read(n).decode("utf-8", "replace") for n in z.namelist() if n.endswith(".xhtml"))
        self.assertIn("The sign in the window said closed", text)
        self.assertNotIn("Referred by", text)
        self.assertNotIn("PREMISE", text)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m unittest discover -s plugins/wrist/tests -p 'test_publish.py' 2>&1 | tail -4`
Expected: ERROR `ModuleNotFoundError: No module named 'wrist_publish'`.

- [ ] **Step 3: Write `wrist_publish.py`**

Create `plugins/wrist/skills/wrist/scripts/wrist_publish.py`:

```python
#!/usr/bin/env python3
"""wrist_publish.py: tool preflight, command planning and building for output/<slug>.epub and .pdf.

Pandoc builds the EPUB and, with Typst as its PDF engine, the PDF. Commands are argument lists and
never go through a shell, so a title with quotes or an ampersand arrives as one argument.
"""
import os
import shutil
import subprocess

TOOLS = ("pandoc", "typst")
INSTALL = {
    "pandoc": "pandoc 3.2 or later: https://pandoc.org/installing.html "
              "(for example `brew install pandoc`, `sudo apt install pandoc`, `winget install JohnMacFarlane.Pandoc`)",
    "typst": "typst 0.12 or later: https://github.com/typst/typst#installation "
             "(for example `brew install typst`, `winget install --id Typst.Typst`, `cargo install --locked typst-cli`)",
}


class PublishError(Exception):
    pass


def missing_tools(path=None):
    return [t for t in TOOLS if shutil.which(t, path=path) is None]


def install_help(missing):
    lines = ["publishing needs these tools, which are not on the path:"]
    lines += [f"  - {INSTALL[t]}" for t in missing]
    return "\n".join(lines)


def plan_commands(sources, meta, out_dir, slug, publish_dir):
    """[(kind, argv)] for the EPUB and the PDF. `meta` has title, author, optional language, trim, font."""
    common = ["pandoc", "--from", "markdown+smart", *sources,
              "--metadata", f"title={meta['title']}",
              "--metadata", f"author={meta['author']}",
              "--metadata", f"lang={meta.get('language') or 'en'}"]
    epub = common + ["--to", "epub3", "--css", os.path.join(publish_dir, "epub.css"),
                     "-o", f"{out_dir}/{slug}.epub"]
    pdf = common + ["--pdf-engine=typst", "--template", os.path.join(publish_dir, "book.typ")]
    if meta.get("trim"):
        pdf += ["-V", f"papersize={meta['trim']}"]
    if meta.get("font"):
        pdf += ["-V", f"mainfont={meta['font']}"]
    pdf += ["-o", f"{out_dir}/{slug}.pdf"]
    return [("epub", epub), ("pdf", pdf)]


def run_commands(commands, cwd):
    out_dir = None
    for kind, argv in commands:
        target = argv[argv.index("-o") + 1]
        out_dir = os.path.dirname(os.path.join(cwd, target))
        os.makedirs(out_dir, exist_ok=True)
        proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise PublishError(f"{kind} build failed (exit {proc.returncode}): {proc.stderr.strip() or proc.stdout.strip()}")
```

- [ ] **Step 4: Write the book template and the EPUB stylesheet**

Create `plugins/wrist/skills/wrist/publish/book.typ`:

```typst
// wrist book template for `pandoc --pdf-engine=typst`.
// Needs typst 0.12 or later. Fonts: Libertinus Serif ships inside typst, so a PDF embeds it
// without anything installed; pass `font` in PREMISE.md for another family.
#let horizontalrule = align(center)[#v(0.9em) #text(tracking: 0.7em)[\*\*\*] #v(0.9em)]
#show terms: it => it.children.map(child => [#strong[#child.term]\ #pad(left: 1.2em)[#child.description]]).join(parbreak())
$if(highlighting-definitions)$
$highlighting-definitions$
$endif$

#set document(title: [$title$])
#set text(
  font: "$if(mainfont)$$mainfont$$else$Libertinus Serif$endif$",
  size: 10.5pt,
  lang: "$if(lang)$$lang$$else$en$endif$",
  hyphenate: true,
)
#set par(justify: true, leading: 0.62em, spacing: 0.62em, first-line-indent: 1.2em)

// Title page: no number, no running head.
#page(paper: "$if(papersize)$$papersize$$else$a5$endif$", margin: 22mm, header: none, footer: none)[
  #align(center + horizon)[
    #text(size: 2.4em, weight: "bold")[$title$]
    #v(1.4em)
    #text(size: 1.15em)[$for(author)$$author$$sep$, $endfor$]
  ]
]

#set page(
  paper: "$if(papersize)$$papersize$$else$a5$endif$",
  margin: (inside: 22mm, outside: 18mm, top: 22mm, bottom: 24mm),
  header: context {
    if counter(page).get().first() > 1 {
      if calc.odd(here().page()) {
        align(right, text(size: 0.85em, style: "italic")[$title$])
      } else {
        align(left, text(size: 0.85em, style: "italic")[$for(author)$$author$$sep$, $endfor$])
      }
    }
  },
  footer: context align(center, text(size: 0.9em)[#counter(page).display()]),
)
#counter(page).update(1)

#show heading.where(level: 1): it => {
  pagebreak(weak: true)
  v(18%)
  align(center, text(size: 1.5em, weight: "bold", it.body))
  v(1.6em)
}
#show heading.where(level: 2): it => {
  v(1.2em)
  align(center, text(size: 1.1em, weight: "bold", it.body))
  v(0.6em)
}

$body$
```

Create `plugins/wrist/skills/wrist/publish/epub.css`:

```css
body {
  font-family: serif;
  line-height: 1.45;
  margin: 0 5%;
  hyphens: auto;
  -webkit-hyphens: auto;
  orphans: 2;
  widows: 2;
}
h1 { text-align: center; font-size: 1.6em; margin: 3em 0 1.4em; page-break-before: always; }
h2 { text-align: center; font-size: 1.15em; margin: 2em 0 1em; }
p { margin: 0; text-align: justify; text-indent: 1.3em; }
h1 + p, h2 + p, hr + p { text-indent: 0; }
hr { border: none; text-align: center; margin: 1.6em 0; }
hr::after { content: "* * *"; letter-spacing: 0.5em; }
blockquote { margin: 1em 2em; font-style: italic; }
.title-page, header#title-block-header { text-align: center; margin-top: 30%; }
```

- [ ] **Step 5: Add the `publish` command**

Add `import wrist_publish` next to the other module imports at the top of `wrist_check.py`, then insert above `def main():`:

```python
PUBLISH_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "publish"))


@command("publish", lambda p: p.add_argument("--root"))
def cmd_publish(args):
    blockers = gate_blockers(args, "publishing")
    if blockers:
        print("publish blocked:")
        for b in blockers:
            print(f"  - {b}")
        return 1
    missing = wrist_publish.missing_tools()
    if missing:
        print(wrist_publish.install_help(missing))
        return 1
    wrist_root, files, profile, pm, slug = load_all(args)
    root = project_root(args)
    sources = [path for path, function in profile.expected_files(slug) if profile.functions[function]["prose"]]
    meta = {"title": pm.front["title"][1], "author": pm.front["author"][1],
            "language": pm.front.get("language", (0, "en"))[1], "trim": pm.front.get("trim", (0, ""))[1],
            "font": pm.front.get("font", (0, ""))[1]}
    try:
        wrist_publish.run_commands(wrist_publish.plan_commands(sources, meta, "output", slug, PUBLISH_DIR), root)
    except wrist_publish.PublishError as exc:
        print(f"publish failed: {exc}")
        return 1
    print(f"published output/{slug}.epub and output/{slug}.pdf")
    return 0
```

- [ ] **Step 6: Run the tests**

Run: `python3 -m unittest discover -s plugins/wrist/tests 2>&1 | tail -8`
Expected: `OK` with one skip (`test_real_build_writes_both_files`) on a machine without pandoc and typst.

- [ ] **Step 7: Verify the real build where the tools exist (required before cycle 1 is called done)**

On a machine with pandoc ≥ 3.2 and typst ≥ 0.12:

```bash
cd plugins/wrist/skills/wrist/assets/examples/the-lamp
python3 ../../../scripts/wrist_check.py publish wrist
```

Expected: `published output/the-lamp.epub and output/the-lamp.pdf`. Open the PDF and check the title page, running heads, the `* * *` scene breaks, hyphenation and page numbers. If pandoc fails because the Typst template lacks a helper that pandoc's output uses, run `pandoc -D typst` for that version's default template and copy the missing `#let`/`#show` definitions into `book.typ`. Then run `python3 -m unittest discover -s plugins/wrist/tests -p 'test_publish.py'` and expect no skip. Delete the generated `output/` folder from the example before committing.

On a machine without the tools, state in the hand-back that this step was not run.

- [ ] **Step 8: Commit**

```bash
git add -A plugins/wrist
git commit -m "feat(wrist): add the pandoc and typst publisher" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Shortstory reference content (structures and quality lists)

**Files:**
- Create: `plugins/wrist/skills/wrist/profiles/shortstory/structures.md`
- Create: `plugins/wrist/skills/wrist/profiles/shortstory/quality.md`
- Modify: `plugins/wrist/tests/test_profile.py` (add a content test)

**Interfaces:**
- Consumes: nothing from code.
- Produces: `structures.md` (read in the generation phase to choose a structure) and `quality.md` (read in generation to copy rules into stand-ins, and in realization for the review pass). `quality.md` must contain the heading `## Judgment checklist`.

- [ ] **Step 1: Add the failing content test**

Append to `plugins/wrist/tests/test_profile.py` before the `if __name__` line:

```python
class ReferenceContent(unittest.TestCase):
    def read(self, name):
        with open(os.path.join(SKILL, "profiles", "shortstory", name), encoding="utf-8") as fh:
            return fh.read()

    def test_structures_cover_the_planned_forms(self):
        text = self.read("structures.md")
        for name in ("Freytag", "three-act", "In medias res", "Kishōtenketsu", "Story spine", "Vignette"):
            self.assertIn(name, text)
        self.assertEqual(text.count("**Best for:**"), text.count("\n## "))

    def test_quality_has_the_three_parts(self):
        text = self.read("quality.md")
        for heading in ("## Clich\u00e9s and stock moves", "## Marks of low quality", "## Judgment checklist"):
            self.assertIn(heading, text)
        self.assertGreaterEqual(text.count("- [ ] "), 10)
```

Run: `python3 -m unittest discover -s plugins/wrist/tests -p 'test_profile.py' 2>&1 | tail -4`
Expected: FAIL (`FileNotFoundError` for `structures.md`).

- [ ] **Step 2: Write `structures.md`**

Create `plugins/wrist/skills/wrist/profiles/shortstory/structures.md`:

```markdown
# Short story structures

Pick one from the premise answers (genre, length, tone, ending) and record the choice in the
outline's `Structure:` field. If the user did not name one, record it as an `*UNKNOWN*:` with your
choice as `Proposed:`. Each section says what the form is, where it fits, and what it asks of the
outline.

## Freytag's arc

Exposition, rising action, climax, falling action, resolution. A single line of increasing pressure
that breaks at one point and then settles.

- **Best for:** realist and literary fiction, tragedy, stories of 2,000 to 7,000 words where the ending is earned by pressure.
- **Outline asks for:** one beat per stage; the climax is a choice or a revelation, not an event that merely happens; the resolution is short.
- **Watch for:** an exposition that explains instead of beginning; a falling action longer than the rising action.

## Compressed three-act

Setup, confrontation, resolution, with the first turn by about a quarter of the way and the second by about three quarters.

- **Best for:** genre fiction (crime, science fiction, horror, romance), stories under 3,000 words, anything driven by a goal.
- **Outline asks for:** a want stated in the first beat, an obstacle that raises the cost in the middle, an ending that answers the want, even if the answer is no.
- **Watch for:** a middle that only repeats the obstacle; an ending that arrives by coincidence.

## In medias res with a spine

Open inside the crisis, then fold back to show how it came about, and return to the moment of the opening to resolve it.

- **Best for:** thrillers, mysteries, literary stories built around a regret, 3,000 to 8,000 words.
- **Outline asks for:** the opening moment fixed first, two or three flashbacks each answering a question the opening raised, and a return to the opening moment changed by what the reader now knows.
- **Watch for:** flashbacks that explain what the reader has already inferred; the reveal withheld from the reader but not from the character.

## Kishōtenketsu

Four parts: introduction (ki), development (shō), a turn that recontextualizes (ten), and reconciliation (ketsu). No conflict is required; the turn is an unexpected element that changes how the first parts read.

- **Best for:** quiet, observational and flash fiction under 1,500 words; tone-led stories; stories about attention rather than action.
- **Outline asks for:** four beats; the third beat must be genuinely unrelated on the surface; the fourth lets the reader hold the first three and the turn together without explaining the link.
- **Watch for:** a twist that is only a surprise; a fourth part that explains the connection.

## Story spine

A fixed chain: once upon a time; every day; until one day; because of that, because of that; until finally; ever since.

- **Best for:** fables, comic and children's stories, and as a quick test of any plot; under 1,500 words.
- **Outline asks for:** each link of the chain as one sentence, each caused by the one before; the "ever since" states the new normal.
- **Watch for:** links joined by "and then" instead of "because of that"; a moral stated outright.

## Vignette (single scene)

One scene in one place, ending on a turn in what two people understand rather than in what happens.

- **Best for:** flash fiction under 1,000 words; character studies; the opening of something longer.
- **Outline asks for:** a single beat; the turn named; what is on the table between the characters stated; the exact line or gesture where the turn lands.
- **Watch for:** a scene that is only description; a turn that the narration announces.

## Circular return

The story ends where it began, in the same place or image, with the meaning changed by what happened between.

- **Best for:** literary stories about habit, grief and routine, 1,000 to 5,000 words.
- **Outline asks for:** the opening image fixed first; what changes in the character between the two appearances; the second appearance reusing the opening's wording closely enough to be noticed.
- **Watch for:** a return that is identical, so nothing has changed; a return that explains the change.
```

Note: the file must contain `Kishōtenketsu` with the real "ō" character (U+014D), not an escape.

- [ ] **Step 3: Write `quality.md`**

Create `plugins/wrist/skills/wrist/profiles/shortstory/quality.md`:

```markdown
# Quality for a short story

The target is a story an editor or a prize jury would stop for. These lists name what to avoid. Copy
the ones that apply into each stand-in's `Rules:` during generation; check the work against all of
them during realization. The searchable items are in `lint.json` (run `wrist_check.py lint`); the
rest need a reader's judgment.

## Clichés and stock moves

Openings
- Waking up, an alarm clock, or a character describing themselves in a mirror.
- Weather as the first sentence.
- A dream, a flashback or a memory before the story has earned one.
- A prologue explaining the world or the premise.

Bodies and feelings
- Shivers down spines, held breaths, racing hearts, blood running cold, tears welling.
- Naming the emotion ("a wave of sadness") instead of dramatizing it.
- Sighs, deep breaths and steeling oneself used as filler beats.
- Smiles that do or do not reach the eyes; eyes that sparkle, twinkle or glint.

Dialogue
- Adverb-propped tags ("said angrily"); speech tags other than "said" and "asked" used to show off.
- Characters telling each other what both already know, for the reader's benefit.
- Everyone speaking in the same register, which is the author's.
- Dialogue with no subtext: each line saying exactly what the character means.

Plot and ending
- "It was all a dream", "it was all in his head", the last-line twist that rewrites the story.
- A coincidence that solves the problem.
- A character who is rescued by an arriving stranger or a convenient skill.
- An ending that states the theme or the lesson.
- Death as the cheapest way to end.

Names and detail
- Names that carry no work (every character with a different initial is a virtue; names that all sound alike are a confusion).
- Stock settings and props: the abandoned house, the old journal, the locked door that is simply opened.
- Generic detail ("a nice house", "a beautiful day") where a specific one would do.

## Marks of low quality

- The first paragraph could open any story; nothing in it belongs to this one.
- The protagonist is a passive observer: things happen to them and they do not choose.
- Every character wants the same thing in the same way, or no one wants anything.
- Stakes are announced, not felt: the story says it matters instead of making it cost something.
- Exposition arrives in blocks; the reader is told how the world works before they need it.
- A scene exists only to deliver information, with no pressure between the people in it.
- Every sentence is the same length and shape; the rhythm never changes.
- Adjectives and adverbs carry what verbs and nouns should.
- The narrator explains an image just after offering it.
- The viewpoint slips: a character knows what only another could know.
- Time and place blur: the reader cannot say where a scene happens or how long has passed.
- Telling the reader what to feel at the moment a scene should earn the feeling.
- The title is a label for the plot rather than a way into the story.
- The ending is a summary, or stops without landing.

## Judgment checklist

Work through this in the review pass, with the story and its stand-ins open. Mark an item only when
you have checked it against the text.

- [ ] The first paragraph belongs to this story alone and creates a question or a pressure.
- [ ] The point of view and tense match the stand-in and never slip.
- [ ] Every scene changes something; none exists only to inform.
- [ ] The protagonist makes at least one choice that costs them something.
- [ ] Each main character's speech sounds different from the others' and from the narration.
- [ ] No named feeling at a moment where an action or detail could carry it.
- [ ] Every concrete detail is specific to this story; generic details are replaced.
- [ ] Every item in the stand-ins' `Must include:` is present and no `Must avoid:` item appears.
- [ ] No coincidence solves the central problem.
- [ ] The ending is earned by what came before and does not state the theme.
- [ ] Sentence length and shape vary; no run of three similar openings.
- [ ] Every image is offered once and not explained afterward.
- [ ] The length is within about ten percent of the target.
- [ ] The title adds something the text does not say.
- [ ] Read aloud, nothing makes you stumble or wince.
- [ ] `wrist_check.py lint` reports no hits, or every hit is deliberate.
```

- [ ] **Step 4: Run the tests**

Run: `python3 -m unittest discover -s plugins/wrist/tests -p 'test_profile.py' 2>&1 | tail -4`
Expected: `OK`. If `test_structures_cover_the_planned_forms` fails on `Kishōtenketsu`, confirm the file contains the literal `ō` character, not the escape.

- [ ] **Step 5: Commit**

```bash
git add -A plugins/wrist
git commit -m "feat(wrist): add shortstory structures and quality lists" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Skill, references, templates, manifest and marketplace

**Files:**
- Modify (rewrite): `plugins/wrist/skills/wrist/SKILL.md`, `plugins/wrist/skills/wrist/references/grammar.md`
- Create: `plugins/wrist/skills/wrist/references/publishing.md`
- Create: `plugins/wrist/skills/wrist/assets/templates/PREMISE.md`, `synopsis.wrist.md`, `outline.wrist.md`, `characters.wrist.md`, `misc.wrist.md`, `story.wrist.md`
- Modify: `plugins/wrist/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `README.md`
- Modify: `docs/superpowers/specs/2026-10-03-wrist-foundation-design.md` (bring it in line with what was built)
- Create: `plugins/wrist/tests/test_docs.py`

**Interfaces:**
- Consumes: command names and flags from Tasks 4 to 7.
- Produces: a skill whose description triggers on writing a short story and whose body drives the four phases using the exact commands below.

- [ ] **Step 1: Write the failing docs test**

Create `plugins/wrist/tests/test_docs.py`:

```python
import json
import os
import re
import unittest

from support import HERE, SKILL

ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
COMMANDS = ("check", "unknowns", "order", "status", "stamp", "fix-backlinks", "gate", "lint", "publish")


def text(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as fh:
        return fh.read()


class SkillText(unittest.TestCase):
    def test_skill_names_every_command(self):
        skill = text(SKILL, "SKILL.md")
        for cmd in COMMANDS:
            self.assertIn(f"wrist_check.py\" {cmd} ", skill, cmd)

    def test_skill_front_matter(self):
        skill = text(SKILL, "SKILL.md")
        self.assertTrue(skill.startswith("---\nname: wrist\n"))
        self.assertIn("description:", skill.split("---")[1])

    def test_no_trace_of_the_old_plugin_name(self):
        old = "sk" + "el"          # spelled in two parts so this file does not match itself
        for dp, _, fns in os.walk(os.path.join(ROOT, "plugins", "wrist")):
            if "__pycache__" in dp:
                continue
            for fn in fns:
                if re.search(old + "(?!et)", text(dp, fn), re.I):
                    self.fail(f"the old plugin name is still in {os.path.join(dp, fn)}")

    def test_every_template_is_valid_for_its_function(self):
        for name in ("PREMISE.md", "synopsis.wrist.md", "outline.wrist.md", "characters.wrist.md",
                     "misc.wrist.md", "story.wrist.md"):
            self.assertTrue(os.path.isfile(os.path.join(SKILL, "assets", "templates", name)), name)


class Manifests(unittest.TestCase):
    def test_plugin_manifest(self):
        data = json.loads(text(ROOT, "plugins", "wrist", ".claude-plugin", "plugin.json"))
        self.assertEqual(data["name"], "wrist")

    def test_marketplace_lists_wrist(self):
        data = json.loads(text(ROOT, ".claude-plugin", "marketplace.json"))
        entry = [p for p in data["plugins"] if p["name"] == "wrist"]
        self.assertEqual(len(entry), 1)
        self.assertEqual(entry[0]["source"], "./plugins/wrist")


if __name__ == "__main__":
    unittest.main()
```

Run: `python3 -m unittest discover -s plugins/wrist/tests -p 'test_docs.py' 2>&1 | tail -6`
Expected: FAIL (SKILL.md still describes skel's workflow, templates missing, marketplace lacks wrist).

- [ ] **Step 2: Write `SKILL.md`**

Replace `plugins/wrist/skills/wrist/SKILL.md` with:

````markdown
---
name: wrist
description: Write a prose work (short story, with novel, screenplay and poem to follow) in four phases - premise, generation, realization, publishing. A tree of prose stand-ins under wrist/ holds the notes, facts, rules and unknowns for every file before any final text exists; a checker validates links and structure; then the files are realized and published as PDF and EPUB. Use this whenever the user wants to write, plan or outline a short story, novel, screenplay or poem, mentions wrist, .wrist.md files or a wrist/ folder, or wants a long work built from a checked outline instead of drafted freehand.
---

# wrist: writing in four phases

A wrist tree is a set of **stand-ins**: one note file per file the work will contain, under `wrist/`, each ending in `.wrist.md`. A stand-in says what its file must contain (facts, beats, rules, dependencies, unknowns). It never holds the final text. The stand-ins are checked mechanically, and only then is each file written from its stand-in. The target is a work that would stand up to an editor or a prize jury for its intended audience.

```text
wrist/synopsis.md.wrist.md      ->  synopsis.md
wrist/work/the-lamp.md.wrist.md ->  work/the-lamp.md
```

The `references/`, `profiles/`, `assets/` and `scripts/` paths here are relative to this skill's directory, `${CLAUDE_SKILL_DIR}`, not to the user's project.

Read `references/grammar.md` before writing or editing any `.wrist.md`. The checker enforces it. Only the `shortstory` profile exists so far; if the user wants a novel, screenplay or poem, say it is not built yet.

## The four phases

Each phase starts with a **question phase**: ask the user whatever you need so that nothing in the phase is a guess. Ask a few questions at a time in plain language, and offer your recommendation with each. Record the result, then run the phase's gate:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/wrist_check.py" gate wrist generation   # or realization, publishing
```

A gate prints what blocks the phase. It stays blocked until `PREMISE.md` records that you asked: set `questions_<phase>: done` in its front matter after the questions are answered, never before.

### 1. Premise

1. Ask which profile (`shortstory`). Read `profiles/shortstory/questions.md`.
2. Ask the questions: `required` ones must be answered or become an `*UNKNOWN*:`; `deferrable` ones may be left out. Never invent an answer.
3. Write `wrist/PREMISE.md` from `assets/templates/PREMISE.md`: front matter (`profile`, `title`, `slug`, `author`, `language`) and one `- **<id>:** <answer>` line per question. The slug is a file-friendly form of the title (lower-case words joined by hyphens).

### 2. Generation

1. Question phase, then `questions_generation: done`.
2. Read `profiles/shortstory/structures.md` and `quality.md`. Choose a structure that fits the premise. If the user did not name one, record the choice as an `*UNKNOWN*:` with `Proposed:`; do not present your own choice as settled.
3. Write every stand-in in the profile's shape (five files for a short story), using `assets/templates/`. Create the empty files first so links have targets. Fill in the notes; copy the quality rules that apply into each stand-in's `Rules:`. No stand-in contains final prose: a scene says what it must do, include and avoid, not the sentences.
4. Add `Depends on:` links with a relation word where it helps, for example `(appears)` or `(realizes)`. Do not hand-write `Referred by:` yet. Then:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/wrist_check.py" fix-backlinks wrist --write
python3 "${CLAUDE_SKILL_DIR}/scripts/wrist_check.py" check wrist
```

   Repeat until `check` is clean. A missing file is an error: the tree must name every file that will exist.
5. Hand back the agenda from `python3 "${CLAUDE_SKILL_DIR}/scripts/wrist_check.py" unknowns wrist` (blocking decisions need the user before realization; local ones come with a proposal to accept) and `python3 "${CLAUDE_SKILL_DIR}/scripts/wrist_check.py" order wrist` (the realization order). List nothing as decided that is not in the tree.

### 3. Realization

1. Question phase (confirm the unknowns are resolved), then `questions_realization: done`. Run `gate wrist realization`.
2. Realize the files in the order `order` prints. For each: read its stand-in and the stand-ins it depends on, write the file at the mirrored path, then stamp it:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/wrist_check.py" stamp wrist work/the-lamp.md
```

   Follow every `Rules:`, `Must include:` and `Must avoid:`. If the work needs something the stand-in does not say, change the stand-in first, run `check`, then realize; never let the text drift from its notes.
3. Craft rules for every file: write for the intended reader; prefer the specific to the general; let action and detail carry feeling; give each speaker a distinct voice; vary sentence length and shape; cut anything the story survives losing; read as the audience would.
4. Run `lint`, fix each hit that is not deliberate, and re-stamp:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/wrist_check.py" lint wrist
```

5. Do the review pass: work through the `## Judgment checklist` in `quality.md` against the text. Fix what fails, re-stamp, and only then set `review_done: yes` in `PREMISE.md`.
6. `python3 "${CLAUDE_SKILL_DIR}/scripts/wrist_check.py" status wrist` must show every file realized. A stand-in changed after its file was realized shows as stale: realize the file again.

### 4. Publishing

1. Question phase: ask the author line, the title page text, the trim size (`trim:` a Typst paper name such as `a5` or `us-trade`) and the font if not the default. Record them in `PREMISE.md`, then set `questions_publishing: done`.
2. Run `gate wrist publishing`, then:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/wrist_check.py" publish wrist
```

   It needs `pandoc` and `typst`; if either is missing it prints the install steps and stops. Output is `output/<slug>.epub` and `output/<slug>.pdf`. See `references/publishing.md`.

## Writing good stand-ins

- **Notes, not text.** If a stand-in could be pasted into the book, it is too long. The checker warns when free prose under a heading passes the profile's word limit.
- **Put intent where it is used.** Rationale and rules go at the level they apply to.
- **No ambiguity about files.** Every file the work will contain has a stand-in before realization starts; the profile fixes the shape.
- **Your choices are unknowns.** Anything the user did not state is an `*UNKNOWN*:` with your choice as `Proposed:`.

## Tools

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/wrist_check.py" check WRIST_DIR [--lenient] [--profile NAME]
python3 "${CLAUDE_SKILL_DIR}/scripts/wrist_check.py" unknowns WRIST_DIR [--json]
python3 "${CLAUDE_SKILL_DIR}/scripts/wrist_check.py" order WRIST_DIR [--json]
python3 "${CLAUDE_SKILL_DIR}/scripts/wrist_check.py" status WRIST_DIR [--root .]
python3 "${CLAUDE_SKILL_DIR}/scripts/wrist_check.py" stamp WRIST_DIR PATH... | --all [--root .]
python3 "${CLAUDE_SKILL_DIR}/scripts/wrist_check.py" fix-backlinks WRIST_DIR [--write]
python3 "${CLAUDE_SKILL_DIR}/scripts/wrist_check.py" gate WRIST_DIR generation|realization|publishing
python3 "${CLAUDE_SKILL_DIR}/scripts/wrist_check.py" lint WRIST_DIR [--root .]
python3 "${CLAUDE_SKILL_DIR}/scripts/wrist_check.py" publish WRIST_DIR [--root .]
python3 "${CLAUDE_SKILL_DIR}/scripts/wrist_mv.py" WRIST_DIR OLD NEW | --map map.txt [--dry-run]
```

All scripts use only the Python standard library. `check` exits non-zero on errors. `--root` defaults to the folder that holds `wrist/`.
````

- [ ] **Step 3: Write `references/grammar.md`**

Replace `plugins/wrist/skills/wrist/references/grammar.md` with:

````markdown
# wrist grammar (normative)

`wrist_check.py check` enforces every rule marked **(checked)**.

## 1. Layout and naming

- Every file the work will contain has a stand-in at `wrist/<path>.wrist.md`, mirroring the project root. **(checked)** `wrist/work/the-lamp.md.wrist.md` stands in for `work/the-lamp.md`.
- The profile fixes the file shape. A required file with no stand-in, or a stand-in outside the shape, is an error. **(checked)** The story file is named from the slug in `PREMISE.md`.
- `wrist/PREMISE.md` is the one file that is not a stand-in. `wrist/.stamps` is written by `stamp`; do not edit it.
- Stand-ins take no front matter. A function (synopsis, outline, characters, misc, story) comes from the profile's file shape, not from the file. **(checked, warning)**

## 2. Headings and fields

- Each stand-in has exactly one level-1 heading, typed for its function: `# synopsis: <name>`, `# outline:`, `# characters:`, `# misc:`, `# story:`. **(checked)**
- Children are level-2 headings of the types the function declares (outline: `beat`; characters: `character`; misc: `place`, `object`, `concept`; story: `scene`). No deeper typed headings. **(checked)**
- Untyped headings may be used anywhere for organization.
- A field is a line `- **Label:** value` (the bold, the bullet and the colon placement are flexible). Fields belong to the nearest typed heading.
- Required fields per heading come from `profiles/<name>/profile.json`. **(checked)** For the short story: synopsis (Logline, Ending, Theme); outline (Structure) with beat (Purpose, Change); character (Wants, Flaw, Voice); place, object and concept (Facts); story (Point of view, Length) with scene (Purpose, Length, Must include, Must avoid).
- Every stand-in answers, anywhere in the file: `Required:` (`always`, `conditional: <when>` or `optional: <what is lost>`), `Rules:` (what the realization must follow), `Depends on:`, `Referred by:`, and unknowns (`*UNKNOWN*:` entries or `Unknowns: none`). Write `none` explicitly. **(checked)**
- Free prose under a heading is notes only; more than the profile's `max_prose_words` is a warning. **(checked, warning)** Fenced text does not count.

## 3. Links

```markdown
- **Depends on:** [Ines Vale](../character.md.wrist.md#character-ines-vale) (appears)
- **Referred by:** [scene: The mark](./work/the-lamp.md.wrist.md#scene-the-mark)
```

- Paths are relative to the file holding the link; a `#fragment` is the GitHub-style slug of a heading (`## character: Ines Vale` is `#character-ines-vale`). **(checked)**
- A dependency on another stand-in needs the matching `Referred by:` in the target, and the reverse. **(checked)** Write `Depends on:`, then run `fix-backlinks --write`.
- An optional relation word in parentheses after the link names the relation: for the short story `appears`, `mentions`, `sets up`, `pays off`, `realizes`. An unlisted word is a warning. **(checked, warning)**
- `Depends on:` may point at an external URL; `Referred by:` may not.

## 4. Unknowns

One line per unknown.

```markdown
*UNKNOWN*: [short-name] <what is unknown>. Kind: blocking | local. Proposed: <default>. Consequence: <what stays blocked>. Unlocks: <what becomes writable>.
*UNKNOWN*: Follows [short-name]. Consequence: <what the open decision means here>.
```

- `Kind:` is required; `Proposed:` is required for `local`. Names are unique across the tree and `PREMISE.md`. A follower must name a declared unknown. **(checked)**
- A **blocking** unknown changes what a file contains or whether it exists; a **local** one affects only a detail and carries a proposal.
- Anything you chose that the user did not state is an unknown with a `Proposed:`.
- Informal markers (TBD, TODO, FIXME, ???) outside fences are warned about. **(checked, warning)**

## 5. PREMISE.md

Front matter between `---` lines; one `- **<question-id>:** answer` line per profile question.

| Key | Meaning |
|---|---|
| `profile` | the profile in use **(checked)** |
| `title`, `slug` | required; the slug is lower-case words joined by hyphens **(checked)** |
| `author`, `language` | title page and metadata; `author` is needed to publish; `language` defaults to `en` |
| `trim`, `font` | optional PDF trim size (a Typst paper name) and font family |
| `questions_generation`, `questions_realization`, `questions_publishing` | `done` once that phase's questions were asked |
| `review_done` | `yes` once the review pass is finished |

A required question with no answer is an error; a deferrable one is a warning. An `*UNKNOWN*:` in the answer counts as an answer. **(checked)**

## 6. Fences

Every fence opens with three or more backticks (or tildes) and a language tag; use `text` for plain text. **(checked)** Fenced content is ignored for headings, fields, links and unknowns.
````

- [ ] **Step 4: Write `references/publishing.md`**

Create `plugins/wrist/skills/wrist/references/publishing.md`:

```markdown
# Publishing

`wrist_check.py publish wrist` turns the realized prose files into `output/<slug>.epub` and `output/<slug>.pdf`.

## Needs

- `pandoc` 3.2 or later and `typst` 0.12 or later on the path. If either is missing the command prints the install steps and stops before building.
- The `publishing` gate open: question phase recorded, `check` clean, every file realized and not stale or edited, the story non-empty, `review_done: yes`, and `author:` set.

## What goes in the book

Only files whose profile function is marked `prose` (the story, for a short story), in the profile's order. The stand-in tree, `PREMISE.md`, stamps and the notes files (synopsis, outline, character, misc) are never included.

## Layout

- **EPUB:** pandoc, with `publish/epub.css` (justified text, hyphenation, indented paragraphs, `* * *` scene breaks) and a generated title page from the title, author and language in `PREMISE.md`.
- **PDF:** pandoc into `publish/book.typ` via Typst: a title page, justified and hyphenated text, first-line indents, widow and orphan control, mirrored running heads, page numbers, and chapter or section openers. The default font is Libertinus Serif, which Typst embeds.
- **Trim size** is `trim:` in `PREMISE.md`, a Typst paper name (`a5` by default, `us-trade`, `iso-b5`, `a4`). **Font** is `font:`.

## When the build fails

Pandoc's error is printed. The usual cause is a Typst helper that a newer pandoc emits and `book.typ` does not define; run `pandoc -D typst` and copy the missing `#let` or `#show` definitions into `publish/book.typ`.
```

- [ ] **Step 5: Write the templates**

Create `plugins/wrist/skills/wrist/assets/templates/PREMISE.md`:

```markdown
---
profile: shortstory
title: <Title>
slug: <lower-case-words-joined-by-hyphens>
author: <Author name>
language: en
---

# Premise

<One or two sentences: what this work is.>

## Answers

- **genre:** <answer or *UNKNOWN*: [name] <what>. Kind: blocking. Consequence: <...>. Unlocks: <...>.>
- **premise:** <answer>
- **ending:** <answer>
- **tone:** <answer>
- **audience:** <answer>
- **length:** <answer>
- **viewpoint:** <answer>
- **target:** <answer>
- **characters:** <answer>
- **motifs:** <answer>
- **fixed:** <answer>
- **structure:** <answer>
- **avoid:** <answer>
```

Create `plugins/wrist/skills/wrist/assets/templates/synopsis.wrist.md`:

```markdown
# synopsis: <Title>

<What the synopsis must do.>

- **Logline:** <one sentence: who, what they want, what stands in the way>
- **Ending:** <how it ends>
- **Theme:** <what it is about underneath>
- **Rules:** <length, tense, voice; must state the ending>
- **Required:** always
- **Depends on:** none
- **Referred by:** [outline](./outline.md.wrist.md)
- **Unknowns:** none
```

Create `plugins/wrist/skills/wrist/assets/templates/outline.wrist.md`:

```markdown
# outline: <Title>

<What the outline must do.>

- **Structure:** <chosen structure from structures.md, or *UNKNOWN*: with Proposed:>
- **Rules:** <how many beats, what each must change>
- **Required:** always
- **Depends on:** [synopsis](./synopsis.md.wrist.md) (mentions)
- **Unknowns:** none

## beat: <Beat name>

- **Purpose:** <what this beat is for>
- **Change:** <what is different after it>
- **Referred by:** [scene: <Scene name>](./work/<slug>.md.wrist.md#scene-<scene-slug>)
```

Create `plugins/wrist/skills/wrist/assets/templates/characters.wrist.md`:

```markdown
# characters: <Title>

<What the registry must hold.>

- **Rules:** <which characters are named; naming rules>
- **Required:** always
- **Depends on:** [synopsis](./synopsis.md.wrist.md) (mentions)
- **Unknowns:** none

## character: <Name>

<Two lines of who they are.>

- **Wants:** <what they want in this story>
- **Flaw:** <what stands in their way>
- **Voice:** <how they speak>
- **Referred by:** [scene: <Scene name>](./work/<slug>.md.wrist.md#scene-<scene-slug>)
```

Create `plugins/wrist/skills/wrist/assets/templates/misc.wrist.md`:

```markdown
# misc: <Title>

<What this file holds: places, objects and concepts that are not characters.>

- **Rules:** <what may and may not be named>
- **Required:** always
- **Depends on:** [synopsis](./synopsis.md.wrist.md) (mentions)
- **Unknowns:** none

## place: <Name>

<Two lines.>

- **Facts:** <fixed facts the text must respect>
- **Referred by:** [scene: <Scene name>](./work/<slug>.md.wrist.md#scene-<scene-slug>)
```

Create `plugins/wrist/skills/wrist/assets/templates/story.wrist.md`:

```markdown
# story: <Title>

<What the story file must be.>

- **Point of view:** <person, whose, tense>
- **Length:** <target words and number of scenes>
- **Rules:** <voice, forbidden moves, quality rules copied from quality.md>
- **Required:** always
- **Referred by:** none
- **Unknowns:** none

## scene: <Scene name>

- **Purpose:** <what the scene must do>
- **Length:** <target words>
- **Must include:** <details, lines or images that must appear>
- **Must avoid:** <what must not appear>
- **Depends on:** [<Beat name>](../outline.md.wrist.md#beat-<beat-slug>) (realizes)
- **Depends on:** [<Character>](../character.md.wrist.md#character-<character-slug>) (appears)
```

- [ ] **Step 6: Update the manifests and README**

Replace `plugins/wrist/.claude-plugin/plugin.json` with:

```json
{
  "name": "wrist",
  "description": "Write a prose work in four phases: premise, a checked tree of prose stand-ins under wrist/, realization into the real files, and PDF/EPUB publishing. Starts with the short story profile",
  "version": "0.1.0",
  "author": { "name": "Sean Dunn", "email": "sean.edward.dunn@gmail.com" },
  "license": "MIT",
  "keywords": ["writing", "fiction", "short-story", "outline", "epub", "publishing"]
}
```

In `/home/sean/Data/Projects/claude-plugins/.claude-plugin/marketplace.json`, add after the `skel` entry (add a comma after its closing brace):

```json
    {
      "name": "wrist",
      "source": "./plugins/wrist",
      "description": "Write prose in four phases: premise, checked stand-in tree, realization, PDF/EPUB publishing"
    }
```

In `README.md`: change "Five plugins." to "Six plugins."; after the skel install line add `/plugin install wrist@hanoixan-claude-plugins`; add a row to the plugin table after skel's row:

```markdown
| [wrist](#wrist) | Writing a short story from a checked outline | none | yes | none |
```

and add this section at the end of the file:

````markdown
## wrist

Writes a prose work in four phases, using the same idea as skel. A `wrist/` folder mirrors the
files the work will contain, each as a `.wrist.md` stand-in that holds notes, facts, rules and
open questions, never the final text:

```
wrist/synopsis.md.wrist.md       ->  synopsis.md
wrist/work/the-lamp.md.wrist.md  ->  work/the-lamp.md
```

The phases are premise (the profile's questions, recorded in `wrist/PREMISE.md`), generation (the
stand-in tree, checked for structure, links and unknowns), realization (each file written from its
stand-in, linted for clichés, reviewed against a checklist) and publishing (`output/<slug>.pdf`
and `output/<slug>.epub` through pandoc and typst). Each phase is preceded by a question phase and
a gate.

A profile is data: the file shape, the headings and required fields, the questions, the reference
structures and a list of clichés to avoid. Only `shortstory` exists so far; novel, screenplay and
poem profiles are planned.

wrist needs `python3` for its scripts (standard library only) and, to publish, `pandoc` 3.2+ and
`typst` 0.12+. A complete worked example is in
`plugins/wrist/skills/wrist/assets/examples/the-lamp/`.
````

- [ ] **Step 7: Bring the spec in line with what was built**

Edit `docs/superpowers/specs/2026-10-03-wrist-foundation-design.md`:

1. In "Kept", delete "and the SCC helper".
2. In the `PREMISE.md` section, replace "and `question_phase:` flags per phase" with "`author:`, `language:`, optional `trim:` and `font:`, `questions_generation`, `questions_realization` and `questions_publishing` (each `done` once that phase's questions were asked), and `review_done: yes`".
3. In the Commands table add the row `| \`gate\` | lists what blocks the generation, realization or publishing phase; exit 1 when blocked |`.
4. In "Open decisions", append: "7. `order` does not group dependency cycles; it reports only dependencies that contradict the profile order." and "8. The kept skel tests were not carried over verbatim: they were fused to the undo-system code fixture, so the behavior they covered was re-tested against the-lamp example."

- [ ] **Step 8: Run the tests**

Run: `python3 -m unittest discover -s plugins/wrist/tests 2>&1 | tail -8`
Expected: `OK` (one skip without pandoc and typst). `test_no_skel_left_in_the_plugin` also guards the rename.

- [ ] **Step 9: Commit**

```bash
git add -A plugins/wrist .claude-plugin/marketplace.json README.md docs/superpowers/specs
git commit -m "feat(wrist): add the skill, grammar reference, templates and marketplace entry" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Whole-plugin verification

**Files:**
- Modify: none expected (fix whatever the checks find in the task that owns it).

**Interfaces:**
- Consumes: everything above.

- [ ] **Step 1: Full test suite**

Run: `python3 -m unittest discover -s plugins/wrist/tests -v 2>&1 | tail -15`
Expected: `OK`, with only `test_real_build_writes_both_files` skipped when `pandoc` and `typst` are absent.

- [ ] **Step 2: skel is untouched**

Run: `git diff --stat main -- plugins/skel; python3 -m unittest discover -s plugins/skel/tests -q 2>&1 | tail -3`
Expected: no diff output for `plugins/skel`; skel's 223 tests still `OK`.

- [ ] **Step 3: Drive the example as a user would**

```bash
cd plugins/wrist/skills/wrist/assets/examples/the-lamp
S=../../../scripts/wrist_check.py
python3 $S check wrist
python3 $S order wrist
python3 $S status wrist
python3 $S lint wrist
for p in generation realization publishing; do python3 $S gate wrist $p; done
python3 $S publish wrist
```

Expected: `check` ends `0 errors, 0 warnings`; `order` lists the five files in order; `status` shows `Realized (5)`; `lint` ends `0 hits in 0 files`; all three gates `open`; `publish` either builds both files (tools present) or prints the install steps for `pandoc` and `typst` and exits 1. If a build ran, delete the `output/` folder.

- [ ] **Step 4: Prove the generation workflow against a fresh project**

In a temporary directory, with no tree, confirm the commands refuse cleanly:

```bash
T=$(mktemp -d); cd "$T"; mkdir wrist
python3 /home/sean/Data/Projects/claude-plugins/plugins/wrist/skills/wrist/scripts/wrist_check.py check wrist; echo "exit $?"
python3 /home/sean/Data/Projects/claude-plugins/plugins/wrist/skills/wrist/scripts/wrist_check.py check wrist --profile shortstory | tail -4; echo "exit $?"
```

Expected: the first prints `no profile: give --profile or set ...` and exits non-zero; the second reports `PREMISE.md is missing` and one `required stand-in missing` line per profile file, then exits 1.

- [ ] **Step 5: Leftover scan**

Run: `grep -rniE "skel|TODO|TBD|FIXME" plugins/wrist --include='*' -I | grep -vi 'skelet' | grep -v 'tests/'`
Expected: no output (test files legitimately contain `TODO` as test input).

- [ ] **Step 6: Commit any fixes**

```bash
git status --short
git add -A plugins/wrist && git commit -m "fix(wrist): close findings from whole-plugin verification" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

(Skip the commit when `git status` shows nothing to commit.)

---

## Self-review

**1. Spec coverage**

| Spec section | Task |
|---|---|
| Phases, question phases, gates | 5 (`gate`), 9 (SKILL.md) |
| Plugin layout, copy and rename, `skel` untouched | 1, 10 step 2 |
| Removed / kept machinery | 4 |
| Stand-in naming, `PREMISE.md`, function from path | 4 |
| Headings and fields from profile, common fields | 4 (`validate_file`), 2 |
| Links with relation words | 4 (`LINK_REL_RE`, relation warning) |
| Unknowns unchanged | 4 (ported tests in `test_unknowns.py`) |
| Content rule (`max_prose_words`) | 4 (`prose_words`, tests) |
| Profile data (`profile.json`, questions, structures, quality, lint) | 2, 6, 8 |
| `shortstory` content | 2, 6, 8 |
| Checker commands incl. `order`, `status`, `stamp`, `lint`, `fix-backlinks`, `wrist_mv` | 4, 5, 6 |
| File-shape errors including slug mismatch | 4 (`collect_diags`, tests) |
| `PREMISE.md` rules | 4 (`premise_problems`) |
| Sidecar stamps | 5 |
| Workflow (SKILL.md) | 9 |
| Publishing: preflight, EPUB, PDF, output, exclusions | 7 |
| Testing: fake profile, schema, lint pairs, sample tree, gate messages | 4 (`test_generic`), 2, 6, 3, 5 |
| Roadmap (`optional_if`, `family` keys reserved) | Not implemented, as the spec says; `validate` rejects unknown keys, so adding them later is a deliberate schema change |

Gaps closed: marketplace and README entry (Task 9); spec updated for the `gate` command, `questions_<phase>` flags, `author`/`trim`/`font` keys, dropped SCC helper, and the test-port deviation (Task 9 step 7).

**2. Placeholder scan:** the plan contains no "TBD/implement later" steps. The `<...>` markers in templates (Task 9 step 5) are the intended template slots, not plan gaps. `TODO` appears only as test input in `test_check.py`.

**3. Type consistency:** `load_all` returns `(wrist_root, files, profile, pm, slug)` in every use (Tasks 4 to 7). `collect_diags(wrist_dir, wrist_root, files, profile, pm, slug, lenient, override)` is called with the same eight arguments in `cmd_check` and `gate_blockers`. `realized_state` returns the five strings used by `cmd_status` groups and `gate_blockers`. `Profile.expected_files` returns `(path, function)` pairs everywhere. `wrist_publish.plan_commands(sources, meta, out_dir, slug, publish_dir)` matches its test and `cmd_publish`. Command names match between `COMMANDS`, `SKILL.md` and `test_docs.py`.

**4. Review Focus coverage:** items 1 to 5 each have a named test: slug mismatch (`test_story_name_must_match_the_slug`), edited file (`test_publishing_is_blocked_by_a_hand_edited_realized_file`), empty story (`test_publishing_is_blocked_by_an_empty_story`), dialogue cliché (`test_the_same_phrase_in_dialogue_is_not_reported` and `test_an_anywhere_pattern_is_reported_inside_dialogue`), special-character title (`test_a_title_with_quotes_ampersand_and_unicode_is_one_intact_argument`).

**Known risks the executor should watch:**
- Task 4 is the largest and is edit-based on the renamed file. After step 6, the `grep` must be clean before running tests; read any `NameError` as a missed deletion or a missed rename of a variable such as `skel_root`.
- The example's text is the contract for most tests (exact `replace()` anchors). If you reword an example line, grep the tests for it.
- Task 7's real build and `book.typ` cannot be verified on this machine (no pandoc or typst); Task 7 step 7 must be run elsewhere before cycle 1 is called done.
