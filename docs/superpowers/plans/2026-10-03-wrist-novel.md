# wrist novel profile (cycle 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the `novel` profile to wrist: optional files and a numbered chapter family fixed by `PREMISE.md`, an `Established:` continuity field, and publishing that assembles a book with front matter, contents and chapters.

**Architecture:** `profile.json` gains `when` and `family` file entries, a `premise_keys` section, and three function-level settings. The profile is bound to the premise values once in `load_all`, so every existing `expected_files(slug)` call keeps its signature and sees the right file set. The novel is data plus an example; publishing adds a Lua filter that builds front matter per output format and a marker file that switches PDF page numbering from roman to arabic.

**Tech Stack:** Python 3.10 standard library (scripts and `unittest`); pandoc 3.12 and typst 0.15 for the real publish tests (installed on this machine; the tests skip when absent).

**Spec:** `docs/superpowers/specs/2026-10-03-wrist-novel-design.md` (builds on `2026-10-03-wrist-foundation-design.md`)

## Global Constraints

- Scripts and tests use only the Python standard library; profiles are JSON.
- Stand-ins are `wrist/<mirrored path>.wrist.md`, one work per project root; `PREMISE.md`, `wrist/.stamps` and the `Depends on:`/`Referred by:` link rules are unchanged.
- The checker stays generic: no novel vocabulary in `wrist_check.py`, `wrist_profile.py`, `wrist_lint.py` or `wrist_publish.py`.
- The short story profile, its example and all of its tests keep passing unchanged.
- File sets are fixed by `PREMISE.md`: a `when` file exists only if its bool key is true; a `family` file expands to `1..N`, `{n}` zero-padded to the width of `N`.
- `premise_keys` types are `bool` (`yes`/`no`/`true`/`false`, default false) and `int` (base-10, within `min`/`max`); a wrong or missing required value is a `check` error.
- `stamp` refuses a realized file whose stand-in lacks a `required_when_realized` field; `gate publishing` reports it, and a first line that does not match the `heading_field`.
- `lint` is advisory (exit 0). `publish` needs `pandoc` and `typst`.
- Stand-ins hold notes, never final text. `plugins/skel/` is not modified.

## Review Focus

Inputs the spec implies that no obvious test would reach. Each has a test in the task that owns the code.

1. Changing `chapters:` after generation (3 to 4, or 9 to 10 so the padding width changes) must fail `check` with "required stand-in missing" and "outside the novel shape", never pass silently. Task 2.
2. `chapters: ten`, `chapters: 0`, `chapters: 201`, a missing `chapters:`, and `forward: maybe` must each give a clear `check` error, not a traceback. Task 2.
3. An `Established:` that is empty, or whose text is on following bullet lines, must be judged correctly by `stamp` and `gate`. Task 2.
4. A realized chapter whose first line does not match its stand-in's `Heading:` must block publishing. Task 2.
5. A copyright or dedication containing `&`, `#`, quotes and non-ASCII characters must reach pandoc intact as one argument and render in the PDF and EPUB. Task 5.

---

## File structure

```text
plugins/wrist/
  skills/wrist/
    scripts/wrist_profile.py      replaced: premise_keys, when/family, function settings, premise binding
    scripts/wrist_check.py        edited: load_all binding, premise rules, helpers, sequence warning, stamp/gate/publish
    scripts/wrist_publish.py      edited: front matter flags, marker file
    profiles/novel/               profile.json, questions.md, structures.md, quality.md, lint.json
    publish/frontmatter.lua       new; book.typ and epub.css edited
    assets/templates/novel/       nine templates
    assets/examples/salt-road/    complete tiny novel
    SKILL.md, references/grammar.md, references/publishing.md   edited
  tests/support.py (edited), test_families.py (new), test_novel_profile.py (new),
        test_novel.py (new), test_publish.py / test_docs.py / test_profile.py (edited)
```

---

### Task 1: Profile engine: premise keys, `when` and `family` files, function settings

**Files:**
- Modify (replace whole file): `plugins/wrist/skills/wrist/scripts/wrist_profile.py`
- Create: `plugins/wrist/tests/test_families.py` (the `ProfileEngine` class)
- Modify: `plugins/wrist/tests/test_profile.py` (two validation tests)

**Interfaces:**
- Consumes: the Task 2 foundation `wrist_profile` API (`parse_profile`, `load_profile`, `Profile.expected_files(slug)`, `function_for(rel, slug)`, `labels()`, `heading_types()`, `lint_items()`).
- Produces, in `wrist_profile`:
  - `Profile.premise_keys: dict` (key → `{"type": "bool"|"int", "min"?, "max"?, "required"?}`), `Profile.options: dict` (resolved values, `{}` until bound), `Profile.option_problems: list[(key, message)]`.
  - `Profile.resolve_options(front: dict[str, str]) -> (values: dict, problems: list[(key, message)])`; `Profile.set_premise(front)` stores both.
  - `Profile.expected_files(slug, options=None) -> list[(path, function)]`, `Profile.function_for(rel, slug, options=None)`; with `options=None` they use the bound `self.options`.
  - `Profile.sequence_prev(slug, options=None) -> dict[rel, previous_rel]` for families whose function has `sequence`.
  - Function spec keys (all defaulted by `parse_profile`): `required_when_realized: list[str]` (default `[]`), `sequence: bool` (`False`), `heading_field: str | None` (`None`). `Profile.labels()` now also returns the `required_when_realized` labels.
  - File entry keys: `when: str`, `family: str`.
  - Message formats (exact): `` `chapters:` is required (a whole number from 1 to 200) ``; `` `chapters:` must be a whole number from 1 to 200 (got 'ten') ``; `` `forward:` must be yes or no (got 'maybe') ``. With no `max`, the range reads `at least <min>`; with no `min`, `from 0`.

- [ ] **Step 1: Write the failing tests**

Create `plugins/wrist/tests/test_families.py`:

```python
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from support import CHECK

import wrist_profile as wp


def mini():
    return {
        "name": "mini",
        "files": [
            {"path": "intro.md", "function": "intro", "order": 1},
            {"path": "work/prologue.md", "function": "part", "order": 2, "when": "prologue"},
            {"path": "work/chapter-{n}.md", "function": "chapter", "order": 3, "family": "chapters"},
        ],
        "premise_keys": {
            "chapters": {"type": "int", "min": 1, "max": 200, "required": True},
            "prologue": {"type": "bool"},
        },
        "functions": {
            "intro": {"heading": "intro"},
            "part": {"heading": "part", "fields": ["Heading"], "heading_field": "Heading", "prose": True},
            "chapter": {"heading": "chapter", "fields": ["Heading"], "heading_field": "Heading",
                        "required_when_realized": ["Noted"], "sequence": True, "prose": True},
        },
        "relations": ["continues", "mentions"],
        "limits": {"max_prose_words": 120},
    }


def bound(**front):
    p = wp.parse_profile(mini())
    p.set_premise({k: str(v) for k, v in front.items()})
    return p


class ProfileEngine(unittest.TestCase):
    def paths(self, p, slug="mini"):
        return [path for path, _ in p.expected_files(slug)]

    def test_a_family_expands_to_one_file_per_number(self):
        self.assertEqual(self.paths(bound(chapters=3)),
                         ["intro.md", "work/chapter-1.md", "work/chapter-2.md", "work/chapter-3.md"])

    def test_numbers_are_zero_padded_to_the_width_of_the_count(self):
        self.assertIn("work/chapter-09.md", self.paths(bound(chapters=10)))
        self.assertNotIn("work/chapter-9.md", self.paths(bound(chapters=10)))
        self.assertIn("work/chapter-001.md", self.paths(bound(chapters=100)))
        self.assertIn("work/chapter-9.md", self.paths(bound(chapters=9)))

    def test_a_when_file_exists_only_when_its_key_is_true(self):
        self.assertNotIn("work/prologue.md", self.paths(bound(chapters=1)))
        self.assertNotIn("work/prologue.md", self.paths(bound(chapters=1, prologue="no")))
        for word in ("yes", "YES", "true", "True"):
            self.assertIn("work/prologue.md", self.paths(bound(chapters=1, prologue=word)))

    def test_order_follows_the_profile_then_the_number(self):
        self.assertEqual(self.paths(bound(chapters=2, prologue="yes")),
                         ["intro.md", "work/prologue.md", "work/chapter-1.md", "work/chapter-2.md"])

    def test_function_for_uses_the_bound_premise(self):
        p = bound(chapters=3)
        self.assertEqual(p.function_for("work/chapter-2.md", "mini"), "chapter")
        self.assertIsNone(p.function_for("work/chapter-4.md", "mini"))
        self.assertIsNone(p.function_for("work/prologue.md", "mini"))

    def test_explicit_options_override_the_bound_ones(self):
        p = bound(chapters=3)
        self.assertEqual(len(p.expected_files("mini", {"chapters": 5, "prologue": False})), 6)

    def test_sequence_prev_links_each_chapter_to_the_one_before(self):
        prev = bound(chapters=3).sequence_prev("mini")
        self.assertEqual(prev, {"work/chapter-2.md": "work/chapter-1.md", "work/chapter-3.md": "work/chapter-2.md"})

    def test_labels_include_fields_that_are_only_required_once_realized(self):
        self.assertIn("Noted", bound(chapters=1).labels())

    def test_an_unbound_profile_has_no_family_files(self):
        p = wp.parse_profile(mini())
        self.assertEqual([path for path, _ in p.expected_files("mini")], ["intro.md"])


class OptionProblems(unittest.TestCase):
    def problems(self, **front):
        p = bound(**front)
        return dict(p.option_problems)

    def test_a_valid_premise_has_no_problems(self):
        self.assertEqual(self.problems(chapters=3, prologue="yes"), {})

    def test_a_missing_required_key(self):
        self.assertEqual(self.problems(), {"chapters": "`chapters:` is required (a whole number from 1 to 200)"})

    def test_a_blank_value_counts_as_missing(self):
        self.assertIn("is required", self.problems(chapters="  ")["chapters"])

    def test_text_is_not_a_number(self):
        self.assertEqual(self.problems(chapters="ten")["chapters"],
                         "`chapters:` must be a whole number from 1 to 200 (got 'ten')")

    def test_out_of_range_numbers(self):
        for value in ("0", "201", "-3", "3.5", "1e2"):
            with self.subTest(value=value):
                self.assertIn("must be a whole number from 1 to 200", self.problems(chapters=value)["chapters"])

    def test_bounds_are_inclusive(self):
        self.assertEqual(self.problems(chapters=1), {})
        self.assertEqual(self.problems(chapters=200), {})

    def test_a_bad_bool(self):
        self.assertEqual(self.problems(chapters=1, prologue="maybe")["prologue"],
                         "`prologue:` must be yes or no (got 'maybe')")

    def test_a_bad_value_leaves_the_file_set_empty_not_broken(self):
        p = bound(chapters="ten", prologue="maybe")
        self.assertEqual([path for path, _ in p.expected_files("mini")], ["intro.md"])

    def test_the_range_reads_at_least_without_a_maximum(self):
        data = mini()
        del data["premise_keys"]["chapters"]["max"]
        p = wp.parse_profile(data)
        p.set_premise({"chapters": "x"})
        self.assertEqual(dict(p.option_problems)["chapters"], "`chapters:` must be a whole number at least 1 (got 'x')")


class SchemaRules(unittest.TestCase):
    def rejected(self, mutate, fragment):
        data = mini()
        mutate(data)
        with self.assertRaises(wp.ProfileError) as cm:
            wp.parse_profile(data)
        self.assertIn(fragment, str(cm.exception))

    def test_when_must_name_a_bool_key(self):
        self.rejected(lambda d: d["files"][1].update(when="chapters"), "'when' must name a bool premise key")
        self.rejected(lambda d: d["files"][1].update(when="nosuch"), "'when' must name a bool premise key")

    def test_family_must_name_an_int_key(self):
        self.rejected(lambda d: d["files"][2].update(family="prologue"), "'family' must name an int premise key")

    def test_a_file_cannot_be_both_when_and_family(self):
        self.rejected(lambda d: d["files"][2].update(when="prologue"), "cannot have both 'when' and 'family'")

    def test_only_a_family_path_may_contain_n(self):
        self.rejected(lambda d: d["files"][2].update(path="work/chapter.md"), "must contain {n}")
        self.rejected(lambda d: d["files"][1].update(path="work/{n}.md"), "must contain {n}")

    def test_unknown_file_key(self):
        self.rejected(lambda d: d["files"][0].update(colour="red"), "unknown key 'colour'")

    def test_premise_key_type(self):
        self.rejected(lambda d: d["premise_keys"]["prologue"].update(type="text"), "'type' must be one of bool, int")

    def test_bounds_only_for_int_keys(self):
        self.rejected(lambda d: d["premise_keys"]["prologue"].update(min=1), "'min' is only for int keys")

    def test_premise_key_unknown_setting(self):
        self.rejected(lambda d: d["premise_keys"]["prologue"].update(colour=1), "unknown key 'colour'")

    def test_heading_field_must_be_one_of_the_fields(self):
        self.rejected(lambda d: d["functions"]["part"].update(heading_field="Nope"),
                      "'heading_field' must be one of its fields")

    def test_a_realized_only_field_cannot_also_be_always_required(self):
        self.rejected(lambda d: d["functions"]["chapter"].update(required_when_realized=["Heading"]),
                      "cannot be both always required and required_when_realized")

    def test_sequence_must_be_a_bool(self):
        self.rejected(lambda d: d["functions"]["chapter"].update(sequence="yes"), "'sequence' must be true or false")

    def test_a_profile_without_premise_keys_still_loads(self):
        data = mini()
        del data["premise_keys"]
        data["files"] = [data["files"][0]]
        self.assertEqual(wp.parse_profile(data).premise_keys, {})

    def test_the_shortstory_profile_is_unchanged(self):
        p = wp.load_profile("shortstory")
        self.assertEqual(p.premise_keys, {})
        self.assertEqual(len(p.expected_files("the-lamp")), 5)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m unittest discover -s plugins/wrist/tests -p test_families.py 2>&1 | tail -4`
Expected: FAILED (the keys, `set_premise` and the new validation do not exist yet).

- [ ] **Step 3: Replace `wrist_profile.py`**

Replace the whole file `plugins/wrist/skills/wrist/scripts/wrist_profile.py` with:

```python
#!/usr/bin/env python3
"""wrist_profile.py: load and validate a wrist profile.

A profile is a folder under profiles/ holding the data the checker reads: profile.json (file
shape, heading types, required fields, premise keys), questions.md, and optionally lint.json.
Standard library only.
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
OPTIONAL_KEYS = {"title_page", "premise_keys"}    # title_page: a separate title page when published (default true)
FUNCTION_KEYS = {"heading", "fields", "children", "prose", "required_when_realized", "sequence", "heading_field"}
FILE_KEYS = {"path", "function", "order", "when", "family"}
KEY_SETTINGS = {"type", "min", "max", "required"}
KEY_TYPES = ("bool", "int")
BOOL_WORDS = {"yes": True, "true": True, "no": False, "false": False}
SCOPES = ("narration", "anywhere")
LINT_KEYS = ("id", "pattern", "label", "note", "scope", "positive", "negative")


class ProfileError(Exception):
    pass


class Question:
    def __init__(self, qid, required, text):
        self.id, self.required, self.text = qid, required, text


def _strings(value):
    return isinstance(value, list) and all(isinstance(v, str) and v for v in value)


def _int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_premise_keys(keys):
    if not isinstance(keys, dict):
        raise ProfileError("'premise_keys' must be an object")
    for kname, kspec in keys.items():
        if not NAME_RE.match(kname) or not isinstance(kspec, dict):
            raise ProfileError(f"premise key '{kname}' needs a valid name and an object")
        extra = sorted(set(kspec) - KEY_SETTINGS)
        if extra:
            raise ProfileError(f"premise key '{kname}' has unknown key {extra[0]!r}")
        if kspec.get("type") not in KEY_TYPES:
            raise ProfileError(f"premise key '{kname}': 'type' must be one of {', '.join(KEY_TYPES)}")
        for bound in ("min", "max"):
            if bound in kspec and (kspec["type"] != "int" or not _int(kspec[bound])):
                raise ProfileError(f"premise key '{kname}': '{bound}' is only for int keys and must be an integer")
        if not isinstance(kspec.get("required", False), bool):
            raise ProfileError(f"premise key '{kname}': 'required' must be true or false")


def validate(data):
    """Raise ProfileError for the first problem in a parsed profile.json."""
    if not isinstance(data, dict):
        raise ProfileError("profile.json must hold an object")
    missing = sorted(TOP_KEYS - set(data))
    if missing:
        raise ProfileError("profile.json is missing " + ", ".join(repr(k) for k in missing))
    extra = sorted(set(data) - TOP_KEYS - OPTIONAL_KEYS)
    if extra:
        raise ProfileError(f"profile.json has unknown key {extra[0]!r}")
    if not isinstance(data.get("title_page", True), bool):
        raise ProfileError("'title_page' must be true or false")
    if not (isinstance(data["name"], str) and NAME_RE.match(data["name"])):
        raise ProfileError("'name' must be lower-case letters, digits and hyphens")
    keys = data.get("premise_keys", {})
    _validate_premise_keys(keys)
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
        if not isinstance(spec.get("sequence", False), bool):
            raise ProfileError(f"function '{fname}': 'sequence' must be true or false")
        if not _strings(spec.get("required_when_realized", [])):
            raise ProfileError(f"function '{fname}': 'required_when_realized' must be a list of labels")
        for label in spec.get("required_when_realized", []):
            if label in spec.get("fields", []):
                raise ProfileError(f"function '{fname}': '{label}' cannot be both always required and "
                                   "required_when_realized")
        heading_field = spec.get("heading_field")
        if heading_field is not None and heading_field not in spec.get("fields", []):
            raise ProfileError(f"function '{fname}': 'heading_field' must be one of its fields")
    files = data["files"]
    if not isinstance(files, list) or not files:
        raise ProfileError("'files' must be a non-empty list")
    seen = set()
    for f in files:
        if not (isinstance(f, dict) and isinstance(f.get("path"), str) and isinstance(f.get("function"), str)
                and _int(f.get("order"))):
            raise ProfileError(f"a files entry needs string 'path', string 'function' and integer 'order': {f!r}")
        extra = sorted(set(f) - FILE_KEYS)
        if extra:
            raise ProfileError(f"file '{f['path']}' has unknown key {extra[0]!r}")
        if f["path"] in seen:
            raise ProfileError(f"'{f['path']}' is listed twice in 'files'")
        seen.add(f["path"])
        if f["function"] not in functions:
            raise ProfileError(f"file '{f['path']}' uses undeclared function '{f['function']}'")
        if "when" in f and "family" in f:
            raise ProfileError(f"file '{f['path']}' cannot have both 'when' and 'family'")
        if "when" in f and keys.get(f["when"], {}).get("type") != "bool":
            raise ProfileError(f"file '{f['path']}': 'when' must name a bool premise key")
        if "family" in f and keys.get(f["family"], {}).get("type") != "int":
            raise ProfileError(f"file '{f['path']}': 'family' must name an int premise key")
        if ("{n}" in f["path"]) != ("family" in f):
            raise ProfileError(f"file '{f['path']}': a family path must contain {{n}}, and only a family path may")
    if not _strings(data["relations"]):
        raise ProfileError("'relations' must be a list of words")
    limits = data["limits"]
    words = limits.get("max_prose_words") if isinstance(limits, dict) else None
    if not (_int(words) and words > 0):
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
        self.title_page = data.get("title_page", True)
        self.premise_keys = data.get("premise_keys", {})
        self.questions = questions
        self.directory = directory
        self.options = {}              # resolved premise values; filled by set_premise
        self.option_problems = []      # [(key, message)]

    def labels(self):
        out = []
        for spec in self.functions.values():
            labels = (list(spec["fields"]) + [f for fs in spec["children"].values() for f in fs]
                      + list(spec["required_when_realized"]))
            for label in labels:
                if label not in out:
                    out.append(label)
        return out

    def heading_types(self):
        types = set()
        for spec in self.functions.values():
            types.add(spec["heading"])
            types.update(spec["children"])
        return types

    def resolve_options(self, front):
        """(values, problems) for the premise keys the profile declares; `front` maps key to its text."""
        values, problems = {}, []
        for key, spec in self.premise_keys.items():
            raw = (front.get(key) or "").strip() or None
            if spec["type"] == "bool":
                values[key] = False
                if raw is None:
                    continue
                if raw.lower() in BOOL_WORDS:
                    values[key] = BOOL_WORDS[raw.lower()]
                else:
                    problems.append((key, f"`{key}:` must be yes or no (got '{raw}')"))
                continue
            values[key] = 0
            low, high = spec.get("min", 0), spec.get("max")
            if high is None:
                span = f"at least {low}"
            else:
                span = f"from {low} to {high}"
            if raw is None:
                if spec.get("required"):
                    problems.append((key, f"`{key}:` is required (a whole number {span})"))
                continue
            if re.fullmatch(r"[0-9]+", raw) and low <= int(raw) and (high is None or int(raw) <= high):
                values[key] = int(raw)
            else:
                problems.append((key, f"`{key}:` must be a whole number {span} (got '{raw}')"))
        return values, problems

    def set_premise(self, front):
        """Bind the premise values, so the file set below follows PREMISE.md."""
        self.options, self.option_problems = self.resolve_options(front)

    def expected_files(self, slug, options=None):
        opts = self.options if options is None else options
        out = []
        for _, f in sorted(enumerate(self.files), key=lambda p: (p[1]["order"], p[0])):
            path = f["path"]
            if "{slug}" in path:
                if not slug:
                    continue
                path = path.replace("{slug}", slug)
            if "when" in f:
                if opts.get(f["when"]):
                    out.append((path, f["function"]))
            elif "family" in f:
                count = opts.get(f["family"]) or 0
                width = len(str(count))
                for n in range(1, count + 1):
                    out.append((path.replace("{n}", str(n).zfill(width)), f["function"]))
            else:
                out.append((path, f["function"]))
        return out

    def function_for(self, rel, slug, options=None):
        return dict(self.expected_files(slug, options)).get(rel)

    def sequence_prev(self, slug, options=None):
        """{file: the file before it} for each family whose function is a `sequence`."""
        prev = {}
        for _, f in enumerate(self.files):
            if "family" in f and self.functions[f["function"]]["sequence"]:
                paths = [p for p, fn in self.expected_files(slug, options) if fn == f["function"]]
                prev.update(zip(paths[1:], paths))
        return prev

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
        if not isinstance(items, list):
            raise ProfileError("lint.json 'items' must be a list")
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


def parse_profile(data, questions_text="", directory=None):
    data = copy.deepcopy(data)
    validate(data)
    for spec in data["functions"].values():
        spec.setdefault("fields", [])
        spec.setdefault("children", {})
        spec.setdefault("prose", False)
        spec.setdefault("sequence", False)
        spec.setdefault("required_when_realized", [])
        spec.setdefault("heading_field", None)
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

- [ ] **Step 4: Run to verify it passes**

Run: `python3 -m unittest discover -s plugins/wrist/tests -q 2>&1 | tail -4`
Expected: `OK` (skips only if pandoc/typst are absent). The whole suite must stay green, including every short story test.

- [ ] **Step 5: Commit**

```bash
git add plugins/wrist
git commit -m "feat(wrist): add premise keys, when and family files, and function settings to profiles" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Checker integration: premise rules, sequence warning, `stamp` and `gate`

**Files:**
- Modify: `plugins/wrist/skills/wrist/scripts/wrist_check.py` (edits E1 to E6 below)
- Modify: `plugins/wrist/tests/test_families.py` (append the `CheckEngine` class)

**Interfaces:**
- Consumes: Task 1's `Profile` API.
- Produces in `wrist_check.py`:
  - `load_all` binds the premise: `profile.set_premise({k: v[1] for k, v in pm.front.items()})`.
  - `premise_problems` appends `profile.option_problems` as errors at the key's line, and treats a question as answered when its id is a premise key with a non-empty front matter value.
  - `field_text(sf, sec, label) -> str`: the label's same-line text, else the text of the lines that follow up to a blank line, the next field or the next heading; `""` when none.
  - `first_line(path) -> str`: first non-blank line of a file, right-stripped (`utf-8-sig`).
  - `missing_when_realized(sf, profile, slug) -> list[str]` (the labels missing or empty); `heading_problem(sf, profile, slug, impl) -> str | None`.
  - `collect_diags` warns, per stand-in, when `profile.sequence_prev(slug)` names a previous file and no `Depends on:` link to its stand-in carries the relation `continues`.
  - `stamp` refuses a file whose stand-in lacks a `required_when_realized` field; `gate publishing` reports missing fields and heading mismatches.
  - Exact messages: stamp `<shown>: its stand-in has no `<label>:` text; fill it in first`; gate `<impl_rel>: its stand-in has no `<label>:` text; fill it in, then stamp` and `<impl_rel> starts with '<first>' but its stand-in's `<field>:` says '<want>'`; sequence warning `no `Depends on:` link to <prev>'s stand-in with the relation `continues``.

- [ ] **Step 1: Write the failing tests**

Append to `plugins/wrist/tests/test_families.py`, before `if __name__ == "__main__":`:

```python
class CheckEngine(unittest.TestCase):
    """The checker run on a project built from the two-key `mini` profile."""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="wrist-fam-")
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        prof = os.path.join(self.dir, "profiles", "mini")
        os.makedirs(prof)
        with open(os.path.join(prof, "profile.json"), "w") as fh:
            json.dump(mini(), fh)
        self.project = os.path.join(self.dir, "project")
        self.env = dict(os.environ, WRIST_PROFILES_DIR=os.path.join(self.dir, "profiles"))
        self.build(3)

    def put(self, rel, text):
        path = os.path.join(self.project, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def read(self, rel):
        with open(os.path.join(self.project, rel), encoding="utf-8") as fh:
            return fh.read()

    def premise(self, chapters=3, prologue=None, extra=""):
        front = ["profile: mini", "title: Mini", "slug: mini", f"chapters: {chapters}"]
        if prologue is not None:
            front.append(f"prologue: {prologue}")
        front += ["questions_generation: done", "questions_realization: done", "questions_publishing: done",
                  "review_done: yes", "author: A. Writer"]
        self.put("wrist/PREMISE.md", "---\n" + "\n".join(front) + extra + "\n---\n\n# Premise\n")

    def chapter_names(self, n):
        width = len(str(n))
        return [str(i).zfill(width) for i in range(1, n + 1)]

    def build(self, n, noted=False, realize=False):
        """A clean project: intro plus n chapters chained with (continues)."""
        shutil.rmtree(self.project, ignore_errors=True)
        self.premise(n)
        self.put("wrist/intro.md.wrist.md",
                 "# intro: Mini\n\n- **Required:** always\n- **Rules:** none\n- **Depends on:** none\n"
                 "- **Referred by:** none\n- **Unknowns:** none\n")
        names = self.chapter_names(n)
        for i, name in enumerate(names):
            lines = [f"# chapter: Chapter {name}", "", f"- **Heading:** `# {i + 1}. Title`",
                     "- **Required:** always", "- **Rules:** none"]
            lines.append(f"- **Depends on:** [Chapter {names[i - 1]}](./chapter-{names[i - 1]}.md.wrist.md) (continues)"
                         if i else "- **Depends on:** none")
            lines.append(f"- **Referred by:** [Chapter {names[i + 1]}](./chapter-{names[i + 1]}.md.wrist.md)"
                         if i + 1 < n else "- **Referred by:** none")
            lines.append("- **Unknowns:** none")
            if noted:
                lines.append("- **Noted:** something happened")
            self.put(f"wrist/work/chapter-{name}.md.wrist.md", "\n".join(lines) + "\n")
            if realize:
                self.put(f"work/chapter-{name}.md", f"# {i + 1}. Title\n\nWords here.\n")

    def run_cli(self, *args):
        proc = subprocess.run([sys.executable, CHECK, *args], cwd=self.project, env=self.env,
                              capture_output=True, text=True)
        return proc.returncode, proc.stdout + proc.stderr

    def check(self):
        return self.run_cli("check", "wrist")

    def test_a_clean_project_passes(self):
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("4 stand-ins", out)
        self.assertIn("0 errors, 0 warnings", out)

    def test_review_focus_raising_the_chapter_count_after_generation(self):
        self.premise(4)
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("required stand-in missing: wrist/work/chapter-4.md.wrist.md", out)

    def test_review_focus_lowering_the_chapter_count_after_generation(self):
        self.premise(2)
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("outside the mini shape", out)

    def test_review_focus_the_padding_width_changes_at_ten(self):
        self.build(10)
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertTrue(os.path.exists(os.path.join(self.project, "wrist/work/chapter-01.md.wrist.md")))
        self.premise(9)
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("required stand-in missing: wrist/work/chapter-1.md.wrist.md", out)
        self.assertIn("outside the mini shape", out)

    def test_review_focus_each_bad_premise_value_is_a_clear_error(self):
        cases = [("chapters: ten", "`chapters:` must be a whole number from 1 to 200 (got 'ten')"),
                 ("chapters: 0", "must be a whole number from 1 to 200 (got '0')"),
                 ("chapters: 201", "must be a whole number from 1 to 200 (got '201')"),
                 ("prologue: maybe", "`prologue:` must be yes or no (got 'maybe')")]
        for line, fragment in cases:
            with self.subTest(line=line):
                self.build(3)
                text = self.read("wrist/PREMISE.md")
                key = line.split(":")[0]
                if key in text:
                    text = "\n".join(l for l in text.split("\n") if not l.startswith(key + ":"))
                self.put("wrist/PREMISE.md", text.replace("---\n\n# Premise", line + "\n---\n\n# Premise", 1))
                code, out = self.check()
                self.assertEqual(code, 1, out)
                self.assertNotIn("Traceback", out)
                self.assertIn(fragment, out)

    def test_review_focus_a_missing_chapters_key(self):
        text = "\n".join(l for l in self.read("wrist/PREMISE.md").split("\n") if not l.startswith("chapters:"))
        self.put("wrist/PREMISE.md", text)
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("`chapters:` is required (a whole number from 1 to 200)", out)
        self.assertNotIn("Traceback", out)

    def test_a_when_file_must_exist_when_its_key_is_true_and_not_otherwise(self):
        self.premise(3, prologue="yes")
        code, out = self.check()
        self.assertIn("required stand-in missing: wrist/work/prologue.md.wrist.md", out)
        self.premise(3, prologue="no")
        self.put("wrist/work/prologue.md.wrist.md", "# part: P\n")
        code, out = self.check()
        self.assertIn("outside the mini shape", out)

    def test_a_chapter_without_a_continues_link_to_the_one_before_is_a_warning(self):
        path = "wrist/work/chapter-2.md.wrist.md"
        text = self.read(path).replace(" (continues)", " (mentions)")
        self.put(path, text)
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("no `Depends on:` link to work/chapter-1.md's stand-in with the relation `continues`", out)

    def test_the_first_chapter_needs_no_continues_link(self):
        code, out = self.check()
        self.assertNotIn("continues", out)

    # --- stamp, gate: required_when_realized and the heading field -------------------------------

    def stamp(self, *paths):
        return self.run_cli("stamp", "wrist", *paths)

    def test_stamp_refuses_a_realized_file_whose_stand_in_lacks_the_field(self):
        self.build(3, realize=True)
        code, out = self.stamp("work/chapter-1.md")
        self.assertEqual(code, 1, out)
        self.assertIn("work/chapter-1.md: its stand-in has no `Noted:` text; fill it in first", out)
        self.assertFalse(os.path.exists(os.path.join(self.project, "wrist/.stamps")))

    def test_stamp_accepts_the_field_on_one_line(self):
        self.build(3, noted=True, realize=True)
        code, out = self.stamp("work/chapter-1.md")
        self.assertEqual(code, 0, out)
        self.assertIn("stamped work/chapter-1.md", out)

    def test_review_focus_an_empty_field_does_not_count(self):
        self.build(3, realize=True)
        path = "wrist/work/chapter-1.md.wrist.md"
        self.put(path, self.read(path) + "- **Noted:**\n\n")
        code, out = self.stamp("work/chapter-1.md")
        self.assertEqual(code, 1, out)
        self.assertIn("no `Noted:` text", out)

    def test_review_focus_text_on_following_bullet_lines_counts(self):
        self.build(3, realize=True)
        path = "wrist/work/chapter-1.md.wrist.md"
        self.put(path, self.read(path) + "- **Noted:**\n  - first fact\n  - second fact\n")
        code, out = self.stamp("work/chapter-1.md")
        self.assertEqual(code, 0, out)

    def test_stamp_all_names_every_chapter_that_owes_the_field(self):
        self.build(3, realize=True)
        code, out = self.stamp("--all")
        self.assertEqual(code, 1, out)
        for n in (1, 2, 3):
            self.assertIn(f"work/chapter-{n}.md: its stand-in has no `Noted:` text", out)

    def ready(self):
        """Three realized, stamped chapters, ready for the publishing gate."""
        self.build(3, noted=True, realize=True)
        self.put("work/intro.md", "text\n")
        code, out = self.stamp("--all")
        self.assertEqual(code, 0, out)

    def gate(self, phase="publishing"):
        return self.run_cli("gate", "wrist", phase)

    def test_the_publishing_gate_is_open_when_everything_is_in_order(self):
        self.ready()
        code, out = self.gate()
        self.assertEqual(code, 0, out)

    def test_the_gate_blocks_when_a_realized_file_lost_its_field(self):
        self.ready()
        path = "wrist/work/chapter-2.md.wrist.md"
        self.put(path, self.read(path).replace("- **Noted:** something happened\n", ""))
        code, out = self.gate()
        self.assertEqual(code, 1, out)
        self.assertIn("work/chapter-2.md: its stand-in has no `Noted:` text; fill it in, then stamp", out)

    def test_review_focus_a_heading_that_does_not_match_blocks_publishing(self):
        self.ready()
        with open(os.path.join(self.project, "work/chapter-2.md"), "w", encoding="utf-8") as fh:
            fh.write("# 2 Title\n\nWords here.\n")
        self.stamp("work/chapter-2.md")
        code, out = self.gate()
        self.assertEqual(code, 1, out)
        self.assertIn("work/chapter-2.md starts with '# 2 Title' but its stand-in's `Heading:` says '# 2. Title'", out)

    def test_a_leading_blank_line_or_bom_does_not_hide_the_heading(self):
        self.ready()
        with open(os.path.join(self.project, "work/chapter-2.md"), "w", encoding="utf-8-sig") as fh:
            fh.write("\n\n# 2. Title\n\nWords here.\n")
        self.stamp("work/chapter-2.md")
        code, out = self.gate()
        self.assertEqual(code, 0, out)

    def test_order_status_and_lint_see_the_family(self):
        self.build(3, noted=True, realize=True)
        code, out = self.run_cli("order", "wrist")
        self.assertEqual([l.split()[1] for l in out.splitlines() if l[:1].isdigit()],
                         ["intro.md", "work/chapter-1.md", "work/chapter-2.md", "work/chapter-3.md"])
        code, out = self.run_cli("status", "wrist")
        self.assertIn("Pending (1):", out)       # intro.md has no realized file yet
        code, out = self.run_cli("lint", "wrist")
        self.assertEqual(code, 0, out)
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m unittest discover -s plugins/wrist/tests -p test_families.py 2>&1 | grep -E "^(FAIL|ERROR):|^Ran|^FAILED|^OK" | head -30`
Expected: FAILED. The `CheckEngine` tests fail because `load_all` does not bind the premise.

- [ ] **Step 3: Apply the six edits to `wrist_check.py`**

Run this script (it asserts that every anchor exists, so a drifted file fails loudly):

```bash
cd /home/sean/Data/Projects/claude-plugins/plugins/wrist/skills/wrist/scripts && python3 - <<'PYEOF'
s = open("wrist_check.py", encoding="utf-8").read()

def rep(old, new):
    global s
    assert old in s, old[:70]
    s = s.replace(old, new, 1)

# E1: bind the premise values to the profile
rep('''    configure(profile)
    wrist_root, files = load_tree(args.wrist_dir)
    return wrist_root, files, profile, pm, pm.front.get("slug", (0, ""))[1]''',
'''    configure(profile)
    profile.set_premise({key: value for key, (_, value) in pm.front.items()})
    wrist_root, files = load_tree(args.wrist_dir)
    return wrist_root, files, profile, pm, pm.front.get("slug", (0, ""))[1]''')

# E2: option problems, and questions answered by premise keys
rep('''    for q in profile.questions:
        answer = pm.answers.get(q.id)
        if answer is None or not answer[1]:''',
'''    for key, message in profile.option_problems:
        out.append(("error", pm.front.get(key, (1, ""))[0], message))
    for q in profile.questions:
        if q.id in profile.premise_keys and pm.front.get(q.id, (0, ""))[1]:
            continue                # answered in the front matter, where the file set is decided
        answer = pm.answers.get(q.id)
        if answer is None or not answer[1]:''')

# E3: helpers for fields that are required once realized, and for the heading line
rep('''def project_root(args):''', '''def field_text(sf, sec, label):
    """A field's text: its value on the label's line, else the lines that follow it up to a blank line,
    the next field or the next heading. An empty string when there is none."""
    for ln, value in own_fields(sec).get(label, []):
        if value.strip():
            return value.strip()
        parts = []
        for line in sf.lines[ln:]:
            if not line.strip() or FIELD_RE.match(line) or HEADING_RE.match(line):
                break
            parts.append(line.strip())
        if parts:
            return " ".join(parts)
    return ""


def first_line(path):
    """The first non-blank line of a file, without trailing space."""
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        for line in fh:
            if line.strip():
                return line.rstrip()
    return ""


def top_section(sf):
    return next((s for s in sf.sections if s.level == 1), None)


def missing_when_realized(sf, profile, slug):
    """Labels the stand-in must hold now that its file exists and does not."""
    function = profile.function_for(sf.impl_rel, slug)
    top = top_section(sf)
    if function is None or top is None:
        return []
    return [label for label in profile.functions[function]["required_when_realized"]
            if not field_text(sf, top, label)]


def heading_problem(sf, profile, slug, impl):
    """A message when the realized file does not start with the line its stand-in's heading field states."""
    function = profile.function_for(sf.impl_rel, slug)
    top = top_section(sf)
    field = profile.functions[function]["heading_field"] if function else None
    if not field or top is None or not os.path.isfile(impl):
        return None
    want = field_text(sf, top, field).strip("` ").strip()
    first = first_line(impl)
    if want and first != want:
        return f"{sf.impl_rel} starts with '{first}' but its stand-in's `{field}:` says '{want}'"
    return None


def project_root(args):''')

# E4: sequence warning, and a shorter list of expected names
rep('''    names = ", ".join(p for p, _ in expected)
    for sf in files.values():
        if sf.function is None:
            sf.err(1, f"this stand-in is outside the {profile.name} shape; the stand-ins are {names}")''',
'''    names = ", ".join(p for p, _ in expected[:12]) + (", ..." if len(expected) > 12 else "")
    for sf in files.values():
        if sf.function is None:
            sf.err(1, f"this stand-in is outside the {profile.name} shape; the stand-ins are {names}")
    by_impl = {sf.impl_rel: sf for sf in files.values()}
    for rel, previous in profile.sequence_prev(slug).items():
        sf, before = by_impl.get(rel), by_impl.get(previous)
        if sf is None or before is None:
            continue
        linked = any(lk.label == "Depends on" and (lk.relation or "").lower() == "continues"
                     and resolve(sf, lk.target)[0] == before.path for lk in sf.all_links())
        if not linked:
            sf.warn(1, f"no `Depends on:` link to {previous}'s stand-in with the relation `continues`")''')

# E5: stamp refuses a file whose stand-in owes a field
rep('''        entry = {"stand_in": stand_in_hash(sf), "realized": file_hash(impl),
                 "date": datetime.date.today().isoformat()}''',
'''        owed = missing_when_realized(sf, profile, slug)
        if owed:
            print(f"{shown}: its stand-in has no `{owed[0]}:` text; fill it in first")
            failed += 1
            continue
        entry = {"stand_in": stand_in_hash(sf), "realized": file_hash(impl),
                 "date": datetime.date.today().isoformat()}''')

# E6: the publishing gate reports owed fields and heading mismatches
rep('''    for path, function in profile.expected_files(slug):
        impl = os.path.join(root, path)
        if profile.functions[function]["prose"] and os.path.isfile(impl):
            with open(impl, encoding="utf-8", errors="replace") as fh:
                if not fh.read().split():
                    blockers.append(f"{path} is empty; there is nothing to publish")''',
'''    for sf in sorted_files(files, profile, slug):
        impl = os.path.join(root, sf.impl_rel)
        if not os.path.isfile(impl):
            continue
        for label in missing_when_realized(sf, profile, slug):
            blockers.append(f"{sf.impl_rel}: its stand-in has no `{label}:` text; fill it in, then stamp")
        problem = heading_problem(sf, profile, slug, impl)
        if problem:
            blockers.append(problem)
    for path, function in profile.expected_files(slug):
        impl = os.path.join(root, path)
        if profile.functions[function]["prose"] and os.path.isfile(impl):
            with open(impl, encoding="utf-8", errors="replace") as fh:
                if not fh.read().split():
                    blockers.append(f"{path} is empty; there is nothing to publish")''')
open("wrist_check.py", "w", encoding="utf-8").write(s)
PYEOF
python3 -m py_compile wrist_check.py && echo compiled
```

- [ ] **Step 4: Run to verify it passes**

Run: `python3 -m unittest discover -s plugins/wrist/tests -q 2>&1 | tail -5`
Expected: `OK`. If a `test_families` case fails, read its diagnostic: either the test fixture (`build()`) is wrong or the checker is; never weaken the assertion.

- [ ] **Step 5: Commit**

```bash
git add plugins/wrist
git commit -m "feat(wrist): check the premise keys, chapter sequence, Established and heading lines" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 3: The novel profile data

**Files:**
- Create: `plugins/wrist/skills/wrist/profiles/novel/profile.json`, `questions.md`, `structures.md`, `quality.md`, `lint.json`
- Create: `plugins/wrist/tests/test_novel_profile.py`

**Interfaces:**
- Consumes: Task 1's schema.
- Produces: profile name `novel`. Question ids (exact, used by the example and the skill): required `genre, premise, ending, tone, audience, length, chapters, viewpoint`; deferrable `subgenre, setting, worldrules, themes, comps, series, characters, events, fixed, structure, avoid, forward, prologue, afterward, index`. Premise keys `chapters` (int 1–200, required) and `forward, prologue, afterward, index` (bool). Stand-in functions as in the spec table. `structures.md` has one `## ` section per structure with `**Best for:**`; `quality.md` has `## Clichés and stock moves`, `## Marks of low quality`, `## Judgment checklist`.

- [ ] **Step 1: Write the failing tests**

Create `plugins/wrist/tests/test_novel_profile.py`:

```python
import os
import re
import unittest

from support import SKILL

import wrist_profile as wp


class NovelProfile(unittest.TestCase):
    def setUp(self):
        self.p = wp.load_profile("novel")
        self.p.set_premise({"chapters": "28", "forward": "yes", "prologue": "no", "afterward": "yes", "index": "no"})

    def paths(self):
        return [path for path, _ in self.p.expected_files("salt-road")]

    def test_file_shape_follows_the_listing_order(self):
        paths = self.paths()
        self.assertEqual(paths[:5], ["synopsis.md", "outline.md", "character.md", "misc.md", "work/forward.md"])
        self.assertEqual(paths[5], "work/chapter-01.md")
        self.assertEqual(paths[-2:], ["work/chapter-28.md", "work/afterward.md"])
        self.assertEqual(len(paths), 4 + 1 + 28 + 1)       # four registries, forward, 28 chapters, afterward
        self.assertNotIn("work/prologue.md", paths)
        self.assertNotIn("work/index.md", paths)

    def test_the_premise_keys_are_declared(self):
        keys = self.p.premise_keys
        self.assertEqual(keys["chapters"], {"type": "int", "min": 1, "max": 200, "required": True})
        for name in ("forward", "prologue", "afterward", "index"):
            self.assertEqual(keys[name]["type"], "bool")

    def test_a_novel_has_a_title_page(self):
        self.assertIs(self.p.title_page, True)

    def test_chapters_are_a_sequence_with_established_and_a_heading(self):
        spec = self.p.functions["chapter"]
        self.assertTrue(spec["sequence"])
        self.assertEqual(spec["required_when_realized"], ["Established"])
        self.assertEqual(spec["heading_field"], "Heading")
        self.assertEqual(spec["children"]["scene"], ["Purpose", "Length", "Must include", "Must avoid"])

    def test_the_prose_functions(self):
        self.assertEqual(sorted(n for n, s in self.p.functions.items() if s["prose"]),
                         ["afterward", "chapter", "forward", "index", "prologue"])

    def test_the_registries(self):
        self.assertEqual(self.p.functions["characters"]["children"]["character"], ["Wants", "Flaw", "Voice", "Arc"])
        self.assertIn("timeline", self.p.functions["misc"]["children"])

    def test_relations_include_continues(self):
        for word in ("appears", "mentions", "sets up", "pays off", "realizes", "continues"):
            self.assertIn(word, self.p.relations)

    def test_questions(self):
        required = {q.id for q in self.p.questions if q.required}
        self.assertEqual(required, {"genre", "premise", "ending", "tone", "audience", "length", "chapters", "viewpoint"})
        deferrable = {q.id for q in self.p.questions if not q.required}
        self.assertEqual(deferrable, {"subgenre", "setting", "worldrules", "themes", "comps", "series", "characters",
                                      "events", "fixed", "structure", "avoid", "forward", "prologue", "afterward",
                                      "index"})

    def test_every_premise_key_has_a_question(self):
        ids = {q.id for q in self.p.questions}
        self.assertLessEqual(set(self.p.premise_keys), ids)


class NovelReferenceContent(unittest.TestCase):
    def read(self, name):
        with open(os.path.join(SKILL, "profiles", "novel", name), encoding="utf-8") as fh:
            return fh.read()

    def test_structures(self):
        text = self.read("structures.md")
        for name in ("Three-act", "Save the Cat!", "Hero's Journey", "Seven-Point", "Five-act", "Fichtean curve",
                     "Story Circle"):
            self.assertIn(name, text)
        sections = [s for s in text.split("\n## ")[1:]]
        for section in sections:
            title = section.split("\n")[0]
            if title.startswith("Genre"):
                continue
            self.assertIn("**Best for:**", section, title)
            self.assertIn("**Spread across the chapters:**", section, title)

    def test_the_genre_table_names_the_genres(self):
        text = self.read("structures.md")
        for genre in ("mystery", "romance", "thriller", "fantasy", "science fiction", "literary", "young adult",
                      "historical", "horror"):
            self.assertIn(genre, text.lower())

    def test_quality_has_its_parts(self):
        text = self.read("quality.md")
        for heading in ("## Clichés and stock moves", "## Marks of low quality", "## Judgment checklist"):
            self.assertIn(heading, text)
        self.assertGreaterEqual(text.count("- [ ] "), 14)
        for phrase in ("midpoint", "Established", "subplot"):
            self.assertIn(phrase, text)

    def test_every_lint_pattern_matches_its_positive_and_not_its_negative(self):
        items = wp.load_profile("novel").lint_items()
        self.assertGreaterEqual(len(items), 29)
        ids = [i["id"] for i in items]
        self.assertEqual(len(ids), len(set(ids)))
        for item in items:
            with self.subTest(item["id"]):
                rx = re.compile(item["pattern"], re.IGNORECASE)
                self.assertTrue(rx.search(item["positive"]), "positive sample does not match")
                self.assertFalse(rx.search(item["negative"]), "negative sample matches")

    def test_the_novel_keeps_the_short_story_patterns_and_adds_its_own(self):
        short = {i["id"] for i in wp.load_profile("shortstory").lint_items()}
        novel = {i["id"] for i in wp.load_profile("novel").lint_items()}
        self.assertLessEqual(short, novel)
        self.assertGreaterEqual(len(novel - short), 8)


if __name__ == "__main__":
    unittest.main()
```


- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m unittest discover -s plugins/wrist/tests -p test_novel_profile.py 2>&1 | tail -4`
Expected: FAILED (`no profile 'novel'`).

- [ ] **Step 3: Write `profile.json`**

Create `plugins/wrist/skills/wrist/profiles/novel/profile.json`:

```json
{
  "name": "novel",
  "title_page": true,
  "premise_keys": {
    "chapters": {"type": "int", "min": 1, "max": 200, "required": true},
    "forward": {"type": "bool"},
    "prologue": {"type": "bool"},
    "afterward": {"type": "bool"},
    "index": {"type": "bool"}
  },
  "files": [
    {"path": "synopsis.md", "function": "synopsis", "order": 1},
    {"path": "outline.md", "function": "outline", "order": 2},
    {"path": "character.md", "function": "characters", "order": 3},
    {"path": "misc.md", "function": "misc", "order": 4},
    {"path": "work/forward.md", "function": "forward", "order": 5, "when": "forward"},
    {"path": "work/prologue.md", "function": "prologue", "order": 6, "when": "prologue"},
    {"path": "work/chapter-{n}.md", "function": "chapter", "order": 7, "family": "chapters"},
    {"path": "work/afterward.md", "function": "afterward", "order": 8, "when": "afterward"},
    {"path": "work/index.md", "function": "index", "order": 9, "when": "index"}
  ],
  "functions": {
    "synopsis": {"heading": "synopsis", "fields": ["Logline", "Ending", "Theme"]},
    "outline": {
      "heading": "outline",
      "fields": ["Structure"],
      "children": {"beat": ["Purpose", "Change"]}
    },
    "characters": {
      "heading": "characters",
      "children": {"character": ["Wants", "Flaw", "Voice", "Arc"]}
    },
    "misc": {
      "heading": "misc",
      "children": {"place": ["Facts"], "object": ["Facts"], "concept": ["Facts"], "timeline": ["Facts"]}
    },
    "forward": {
      "heading": "forward",
      "fields": ["Heading", "Purpose", "Voice", "Must include", "Must avoid"],
      "heading_field": "Heading",
      "prose": true
    },
    "prologue": {
      "heading": "prologue",
      "fields": ["Heading", "Purpose", "Voice", "Must include", "Must avoid"],
      "heading_field": "Heading",
      "prose": true
    },
    "chapter": {
      "heading": "chapter",
      "fields": ["Heading", "Point of view", "Length"],
      "heading_field": "Heading",
      "required_when_realized": ["Established"],
      "sequence": true,
      "children": {"scene": ["Purpose", "Length", "Must include", "Must avoid"]},
      "prose": true
    },
    "afterward": {
      "heading": "afterward",
      "fields": ["Heading", "Purpose", "Voice", "Must include", "Must avoid"],
      "heading_field": "Heading",
      "prose": true
    },
    "index": {
      "heading": "index",
      "fields": ["Heading"],
      "heading_field": "Heading",
      "prose": true
    }
  },
  "relations": ["appears", "mentions", "sets up", "pays off", "realizes", "continues"],
  "limits": {"max_prose_words": 120}
}
```

- [ ] **Step 4: Write `questions.md`**

Create `plugins/wrist/skills/wrist/profiles/novel/questions.md`:

```markdown
# Premise questions: novel

Ask these in the premise phase, a few at a time, in plain language. A `required` question must be
answered or recorded as an `*UNKNOWN*:` before generation; a `deferrable` question may be left out
(write `none (skipped on purpose)` so `check` stops warning about it). The id is the key used in
`wrist/PREMISE.md`.

Five answers decide which files exist, so they go in the `PREMISE.md` front matter as well as being
asked here: `chapters` (a whole number), and `forward`, `prologue`, `afterward`, `index` (each `yes`
or `no`). Changing one later means changing the tree. A question whose id is one of these keys counts
as answered when the front matter has the key.

## The book

- [required] genre: What is the genre or blend of genres (literary, mystery, romance, thriller, fantasy, science fiction, horror, historical, young adult)?
- [required] premise: What is the central situation, or the question the book turns on, in a paragraph?
- [required] ending: What shape should the ending take (closed, open, ironic, reversal, bittersweet, a cliffhanger for a sequel)?
- [required] tone: What tone should the book hold, and where, if anywhere, may it shift?
- [deferrable] subgenre: Is there a narrower subgenre or comparable shelf (cozy mystery, space opera, domestic noir, and so on)?
- [deferrable] themes: What is the book about underneath the plot?

## The reader and the form

- [required] audience: Who is the intended reader, including the age category (adult, young adult, middle grade)?
- [required] length: What is the target length in words?
- [required] chapters: How many chapters? If you are not sure, I will propose a count from the length and the structure; the number is then fixed for the tree.
- [required] viewpoint: Whose point of view, in which person and tense, and is it one point-of-view character or several?
- [deferrable] comps: Which published books would sit next to this one?
- [deferrable] series: Is it a standalone, or the start of a series? How much should the ending leave open?

## The world and what you already know

- [deferrable] setting: Where and when does it take place?
- [deferrable] worldrules: What rules of the world must hold (magic, technology, law, geography)?
- [deferrable] characters: Which characters do you already want fixed, and what do you know about them?
- [deferrable] events: Which events must happen, and roughly where in the book?
- [deferrable] fixed: Which places, facts or real details must appear exactly?
- [deferrable] structure: Do you have a structure in mind (see structures.md), or should one be proposed from the answers above?
- [deferrable] avoid: What do you want kept out (subjects, tropes, kinds of language)?

## The parts around the chapters

- [deferrable] forward: Does the book need a forward? Say why, and answer `yes` or `no`.
- [deferrable] prologue: Does it need a prologue? Say why, and answer `yes` or `no`.
- [deferrable] afterward: Does it need an afterward? Say why, and answer `yes` or `no`.
- [deferrable] index: Does it need an index? Say why, and answer `yes` or `no`.
```

- [ ] **Step 5: Write `structures.md`**

Create `plugins/wrist/skills/wrist/profiles/novel/structures.md`:

```markdown
# Novel structures

Pick one from the premise answers (genre, length, tone, ending) and record the choice in the outline's
`Structure:` field. If the user did not name one, record it as an `*UNKNOWN*:` with your choice as
`Proposed:`. Each section says what the form is, where it fits, how its beats spread across the chapter
count, what the outline must hold, and what to watch for. The percentages are of the whole book; for 24
chapters, 1% is about a quarter of a chapter, so round to the nearest chapter boundary.

## Three-act

Setup, confrontation, resolution. The first act ends in a point of no return, the second in a low point
that forces the final choice.

- **Best for:** most genre fiction; a safe default when the premise is goal-driven.
- **Spread across the chapters:** act one 0-25% (24 chapters: 1-6), act two 25-75% (7-18) with a midpoint turn near 50% (chapter 12), act three 75-100% (19-24).
- **Outline asks for:** the inciting incident, the first turn, the midpoint turn, the low point, the climax and the resolution, each as a beat tied to a chapter.
- **Watch for:** a second act that only repeats the obstacle; no midpoint turn; a climax the protagonist does not cause.

## Save the Cat!

Fifteen beats: opening image, theme stated, set-up, catalyst, debate, break into two, B story, fun and games, midpoint, bad guys close in, all is lost, dark night of the soul, break into three, finale, final image.

- **Best for:** commercial fiction with a clear hero and a clear want: thrillers, romance, middle grade, young adult, comic novels.
- **Spread across the chapters:** catalyst 10% (chapter 3), break into two 20% (5), midpoint 50% (12), all is lost 75% (18), break into three 80% (19), finale 80-99% (19-23), final image 100% (24).
- **Outline asks for:** all fifteen beats named, the theme stated once, the opening and final images as a pair that shows the change.
- **Watch for:** beats that are present but do not change anything; a theme stated by every character; a formula showing through.

## Hero's Journey

Twelve stages: ordinary world, call to adventure, refusal, meeting the mentor, crossing the threshold, tests and allies and enemies, approach, ordeal, reward, the road back, resurrection, return with the elixir.

- **Best for:** fantasy, science fiction, quest and coming-of-age stories.
- **Spread across the chapters:** ordinary world 0-8% (24 chapters: 1-2), threshold 20-25% (5-6), ordeal 50% (12), road back 75% (18), resurrection 90% (22), return 95-100% (23-24).
- **Outline asks for:** each stage as a beat, the ordeal as a real loss, and what the hero brings back that the ordinary world lacks.
- **Watch for:** a mentor who exists only to die or to explain; a chosen one with no cost; a return that changes nothing.

## Seven-Point

Hook, plot turn one, pinch one, midpoint, pinch two, plot turn two, resolution. Plan backwards from the resolution, and start at the hook's opposite.

- **Best for:** plot-driven books where the ending is fixed first: mysteries, thrillers, series installments.
- **Spread across the chapters:** hook chapter 1, turn one 25% (chapter 6), pinch one 37% (9), midpoint 50% (12), pinch two 62% (15), turn two 75% (18), resolution 100% (24).
- **Outline asks for:** the resolution written first, the hook as its opposite, and the pinches as moments the antagonist's pressure is felt.
- **Watch for:** pinches that do not change the plan; a midpoint that is only a reveal and not a change of approach.

## Five-act (Freytag)

Exposition, rising action, climax, falling action, resolution (denouement).

- **Best for:** literary and historical fiction, tragedy, ensemble books.
- **Spread across the chapters:** exposition 0-15% (24 chapters: 1-3), rising action 15-50% (4-12), climax 50-60% (12-14), falling action 60-85% (15-20), resolution 85-100% (21-24).
- **Outline asks for:** a climax that is a choice or a revelation, a falling action that carries consequences, and a resolution short enough to feel earned.
- **Watch for:** an exposition that explains; a falling action longer than the rising action; a climax at the very end with nothing after it.

## Fichtean curve

No long set-up: the book opens in a crisis and runs through a series of rising crises to one climax, with brief falling action.

- **Best for:** thrillers, horror, fast mystery, anything with a clock.
- **Spread across the chapters:** crisis one in chapter 1, then a new crisis every 3-4 chapters (24 chapters: 1, 4, 8, 12, 16, 20), climax 90% (22), resolution 90-100% (23-24).
- **Outline asks for:** each crisis larger than the last, backstory released in pieces during action, and the climax as the largest crisis.
- **Watch for:** crises that are only noise; exhaustion in the middle; no room to breathe before the climax.

## Story Circle

Eight steps: you (a character in a zone of comfort), need, go, search, find, take, return, change.

- **Best for:** character-led stories, television-shaped seasons, quieter books where change matters more than plot.
- **Spread across the chapters:** you and need 0-12% (24 chapters: 1-3), go 12-25% (4-6), search 25-50% (7-12), find 50% (12), take 50-75% (13-18), return 75-90% (19-22), change 90-100% (23-24).
- **Outline asks for:** the need stated early, the price paid at "take", and the change shown by contrast with step one.
- **Watch for:** a "change" the character announces rather than shows; a "find" that is only information.

## Genre defaults

A starting point, never a rule. Offer these, and let the premise override them.

| Genre | Start from | Why |
|---|---|---|
| mystery | Seven-Point, or Three-act | the resolution is fixed first and clues need placing |
| romance | Save the Cat!, or Three-act | the two leads' beats (meeting, obstacle, black moment) map onto the fifteen beats |
| thriller | Fichtean curve, or Save the Cat! | pressure never drops |
| fantasy | Hero's Journey, or Three-act | the quest shape fits a long, world-heavy book |
| science fiction | Three-act, or Hero's Journey | a premise-led book needs a clear act structure to carry the idea |
| literary | Five-act, or Story Circle | change and consequence matter more than escalation |
| young adult | Save the Cat!, or Story Circle | clear want, fast opening, a visible change |
| historical | Five-act, or Three-act | events often fix the shape; use the structure to choose what to dramatize |
| horror | Fichtean curve, or Three-act | dread builds through a series of rising crises |
```

- [ ] **Step 6: Write `quality.md`**

Create `plugins/wrist/skills/wrist/profiles/novel/quality.md`:

```markdown
# Quality for a novel

The target is a book an editor or a prize jury would stop for. These lists name what to avoid. Copy the
ones that apply into each stand-in's `Rules:` during generation; check the work against all of them during
realization. The searchable items are in `lint.json` (run `wrist_check.py lint`); the rest need a reader's
judgment, per chapter and across the whole book.

## Clichés and stock moves

Openings
- The chosen one, the farm boy, the orphan who learns of a destiny.
- Waking up, an alarm clock, a mirror description, the weather, the sun rising.
- A prologue that explains the world, the prophecy or the history.
- A dream used as a first scene, or a flashback before the book has earned one.

Characters
- The mentor who dies so the hero can grow.
- The villain who explains the plan, or who monologues before the final move.
- An ensemble in which everyone speaks in the author's voice.
- The love interest who exists only to be rescued, or lost.
- Names that sound alike, or that all start with the same letter.

Plot
- A coincidence that solves the central problem.
- A secret kept only because no one asks the obvious question.
- The ally who turns out to be the traitor, with no earlier sign.
- A last-minute rescue by an arriving stranger or an unplanted skill.
- An epilogue that ties every thread, or that tells the reader what to feel.

Prose
- Bodily clichés (shivers, held breaths, racing hearts) and named emotions ("a wave of sadness").
- Stalling gestures (sighs, deep breaths, nods) used between lines of dialogue.
- Adverb-propped dialogue tags; characters telling each other what both know.
- Information delivered in dialogue ("as you know").
- "Suddenly", "meanwhile", "little did she know", "everything was about to change".

## Marks of low quality

- A sagging middle: the second act repeats the obstacle at the same size.
- No midpoint turn, so the book runs in one direction from the inciting incident to the end.
- Stakes that do not escalate, or are announced rather than felt.
- A protagonist who makes no decision in the second act.
- Subplots that start and stop without resolving, or resolve by accident.
- Point-of-view slips: a character knows what only another could know.
- Chapters that all end the same way (always a cliffhanger, always a quiet reflection).
- Verbal tics repeated across chapters (a gesture, a phrase, a kind of simile).
- Exposition in blocks, or backstory before the reader needs it.
- Characters who change because the plot says so, not because of a choice.
- Time and place that blur: the reader cannot say where a chapter is or how long has passed.
- Names, dates, injuries and facts that disagree between chapters.
- An ending that summarizes, or that stops without landing.

## Judgment checklist

Work through this in the review pass, with the realized text and the stand-ins open. Do it once per chapter as
you finish it, and again for the whole book before `review_done: yes`. Mark an item only when you have
checked it against the text.

Per chapter
- [ ] The chapter's first line belongs to this chapter and creates a question or a pressure.
- [ ] The chapter changes something: a fact, a relationship, a plan, a risk.
- [ ] The point of view is the one the stand-in names, and never slips.
- [ ] The chapter ends differently from the chapter before it.
- [ ] Every item in `Must include:` is present and no `Must avoid:` item appears.
- [ ] Nothing in the text contradicts the `Established:` fields of earlier chapters, unless a stand-in names the contradiction as deliberate.
- [ ] The `Established:` field of this chapter lists every new fact, date, injury and promise the text fixed.
- [ ] No fact appears in the text that no stand-in holds.

Whole book
- [ ] There is a midpoint turn, and the second half is not the first half again.
- [ ] Stakes escalate from act to act and are paid, not announced.
- [ ] The protagonist makes a costly decision in the second act.
- [ ] Every subplot resolves, or is left open on purpose and says so in a stand-in.
- [ ] Each main character speaks differently from the others and from the narration.
- [ ] No coincidence solves the central problem.
- [ ] The ending is earned by what came before and does not state the theme.
- [ ] No verbal tic repeats across chapters more than twice.
- [ ] The length is within about ten percent of the target.
- [ ] `wrist_check.py lint` reports no hits, or every hit is deliberate.
```

- [ ] **Step 7: Generate `lint.json`**

The novel's file is the short story's 21 items plus 8 new ones. Create it with this script, then run the tests:

```bash
cd /home/sean/Data/Projects/claude-plugins/plugins/wrist/skills/wrist/profiles && python3 - <<'PYEOF'
import json
short = json.load(open("shortstory/lint.json", encoding="utf-8"))["items"]
extra = [
 {"id": "chosen-one", "pattern": "\\bthe chosen one\\b", "label": "stock hero", "note": "A destiny stands in for a want; give the character a choice.", "scope": "narration",
  "positive": "He was the chosen one.", "negative": "She chose one of the doors."},
 {"id": "meanwhile", "pattern": "\\bmeanwhile\\b", "label": "stock transition", "note": "Cut to the other scene without announcing it.", "scope": "narration",
  "positive": "Meanwhile, across town, the villain waited.", "negative": "She drank her wine."},
 {"id": "everything-changed", "pattern": "\\beverything (?:was about to )?change[sd]?\\b", "label": "announced turn", "note": "Let the change arrive in the scene, not in a promise.", "scope": "narration",
  "positive": "Everything was about to change.", "negative": "She changed the bulb."},
 {"id": "no-idea", "pattern": "\\b(?:she|he|they) had no idea\\b", "label": "authorial intrusion", "note": "Foreshadow with an image, not a warning.", "scope": "narration",
  "positive": "She had no idea what was coming.", "negative": "She had an idea."},
 {"id": "unbeknownst", "pattern": "\\bunbeknownst to\\b", "label": "authorial intrusion", "note": "The narrator knows more than the point-of-view character; keep the point of view close.", "scope": "narration",
  "positive": "Unbeknownst to him, the door was open.", "negative": "He knew the door was open."},
 {"id": "eyes-widened", "pattern": "\\beyes (?:widened|went wide|grew wide)\\b", "label": "stock reaction", "note": "Show the surprise in what the character does.", "scope": "narration",
  "positive": "Her eyes widened.", "negative": "Her eyes were wide-set."},
 {"id": "sun-rose-opening", "pattern": "^\\s*the sun (?:rose|was rising|began to rise|crept)", "label": "stock opening", "note": "A sunrise opening says nothing about this book.", "scope": "narration",
  "positive": "The sun rose over the hills.", "negative": "She watched the sun rise."},
 {"id": "single-tear", "pattern": "\\ba single tear\\b", "label": "stock reaction", "note": "Let the reader supply the tear.", "scope": "narration",
  "positive": "A single tear ran down her cheek.", "negative": "A single sack of salt remained."},
]
import os
os.makedirs("novel", exist_ok=True)
json.dump({"items": short + extra}, open("novel/lint.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
open("novel/lint.json", "a", encoding="utf-8").write("\n")
print(len(short), "+", len(extra))
PYEOF
cd /home/sean/Data/Projects/claude-plugins && python3 -m unittest discover -s plugins/wrist/tests -p test_novel_profile.py 2>&1 | tail -5
```

Expected: `21 + 8`, then `OK` for `test_novel_profile.py`.

- [ ] **Step 8: Run the whole suite and commit**

Run: `python3 -m unittest discover -s plugins/wrist/tests -q 2>&1 | tail -3` (expect `OK`).

```bash
git add plugins/wrist
git commit -m "feat(wrist): add the novel profile data" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 4: The salt-road example novel and its tests

**Files:**
- Create: `plugins/wrist/skills/wrist/assets/examples/salt-road/` (PREMISE, 8 stand-ins, 4 realized notes files, forward, 3 chapters, generated `.stamps`)
- Modify: `plugins/wrist/tests/support.py` (a `NovelCase`)
- Create: `plugins/wrist/tests/test_novel.py`

**Interfaces:**
- Consumes: Tasks 1 to 3.
- Produces: example project with slug `salt-road`: `chapters: 3`, `forward: yes`, no prologue, afterward or index. Stand-ins: `synopsis.md`, `outline.md`, `character.md`, `misc.md`, `work/forward.md`, `work/chapter-1.md`, `work/chapter-2.md`, `work/chapter-3.md` (8). Realized files exist for all 8, all stamped, every chapter has a filled `Established:`. Must pass `check` with 0 errors and 0 warnings and open all three gates. `support.py` adds `NOVEL` (the example path), path constants `N_PREMISE`, `N_OUTLINE`, `N_CHAPTER1`, `N_CHAPTER2`, `N_CHAPTER3`, and `class NovelCase(TreeCase)` (same helpers, copies the novel example).

- [ ] **Step 1: Write the premise**

Create `plugins/wrist/skills/wrist/assets/examples/salt-road/wrist/PREMISE.md`:

```markdown
---
profile: novel
title: Salt Road
slug: salt-road
author: Ada Example
language: en
chapters: 3
forward: yes
prologue: no
afterward: no
index: no
copyright: © 2026 Ada Example. All rights reserved.
dedication: For the carters.
epigraph: "Salt keeps what it is given." — a carter's saying
questions_generation: done
questions_realization: done
questions_publishing: done
review_done: yes
---

# Premise

A worked example: a miniature novel in three chapters.

## Answers

- **genre:** Quiet literary adventure.
- **premise:** A salt carter racing the tide to the sea gate finds a stowaway boy and must decide what to pay the toll keeper.
- **ending:** Bittersweet: she pays the toll with the whole load and crosses with the boy.
- **tone:** Dry and warm, tightening toward the gate.
- **audience:** Adult readers of literary fiction.
- **length:** About 400 words, as a demonstration.
- **viewpoint:** Close third person on Odile, past tense.
- **subgenre:** None.
- **themes:** What you carry is what you owe.
- **comps:** None.
- **series:** Standalone.
- **setting:** A coastal salt road, no named country, an unspecified past.
- **worldrules:** The sea gate closes at dusk and does not reopen until morning.
- **characters:** Odile Marsh, a salt carter; Pim, a boy; Brannock, the toll keeper.
- **events:** The toll is paid in full; they cross as the gate closes.
- **fixed:** The left wheel squeals.
- **structure:** Three-act, one chapter per act.
- **avoid:** Backstory, a chosen-one boy, a villain.
```

- [ ] **Step 2: Write the registry stand-ins**

Create `.../salt-road/wrist/synopsis.md.wrist.md`:

```markdown
# synopsis: Salt Road

Notes for the one-paragraph synopsis of the book.

- **Logline:** A salt carter racing the tide to the sea gate finds a stowaway boy and must decide what to pay the toll keeper.
- **Ending:** She pays the toll with the whole load and walks the last mile with the boy.
- **Theme:** What you carry is what you owe.
- **Rules:** One paragraph, present tense, under 120 words, and it states the ending.
- **Required:** always
- **Depends on:** none
- **Unknowns:** none
```

Create `.../salt-road/wrist/outline.md.wrist.md`:

```markdown
# outline: Salt Road

Notes for the outline of the book.

- **Structure:** Three-act, one chapter per act: the load, the toll, the gate.
- **Rules:** Three beats only. Each beat changes what Odile will do next.
- **Required:** always
- **Depends on:** [synopsis](./synopsis.md.wrist.md) (mentions)
- **Unknowns:** none

## beat: The load

- **Purpose:** Set up the road, the cart and the tide's clock, and bring in the stowaway.
- **Change:** Odile finds Pim under the tarpaulin and lets him ride.

## beat: The toll

- **Purpose:** Confront Brannock with the cost of the crossing.
- **Change:** Odile gives up the whole load.

## beat: The gate

- **Purpose:** Resolve by action: cross before the gate closes.
- **Change:** Odile walks beside the cart instead of driving it alone.
```

Create `.../salt-road/wrist/character.md.wrist.md`:

```markdown
# characters: Salt Road

Notes for the registry of characters.

- **Rules:** Only Odile Marsh, Pim and Brannock are named.
- **Required:** always
- **Depends on:** [synopsis](./synopsis.md.wrist.md) (mentions)
- **Unknowns:** none

## character: Odile Marsh

A salt carter who works the road alone.

- **Wants:** To reach the gate before the tide closes it.
- **Flaw:** Never asks for help.
- **Voice:** Short and practical.
- **Arc:** From carrying everything alone to sharing the road.

## character: Pim

A boy who hides under the tarpaulin.

- **Wants:** To see the sea.
- **Flaw:** Lies before he thinks.
- **Voice:** Quick and wheedling.
- **Arc:** Tells one true thing at the toll house.

## character: Brannock

The toll keeper.

- **Wants:** To collect the toll in full.
- **Flaw:** Rigid.
- **Voice:** Formal, ledger words.
- **Arc:** Bends once, by doing nothing.
```

Create `.../salt-road/wrist/misc.md.wrist.md`:

```markdown
# misc: Salt Road

Notes for places, objects and the clock.

- **Rules:** Only these entries; nothing else is named.
- **Required:** always
- **Depends on:** [synopsis](./synopsis.md.wrist.md) (mentions)
- **Unknowns:** none

## place: The salt road

A straight road between salt pans, white on both sides.

- **Facts:** The road runs from the pans to the sea gate. Milestones mark it.

## place: The sea gate

- **Facts:** A chain gate on the shore road. The keeper lets the chain run slack at dusk and it stays closed until morning.

## object: The salt cart

- **Facts:** A horse-drawn cart carrying forty sacks under a tarpaulin. The left wheel squeals when pushed.

## timeline: The tide

- **Facts:** The tide is an hour behind her at the start. The gate closes at dusk.
```

- [ ] **Step 3: Write the forward and chapter stand-ins**

Create `.../salt-road/wrist/work/forward.md.wrist.md`:

```markdown
# forward: Salt Road

Notes for the forward.

- **Heading:** `# Foreword`
- **Purpose:** A carter's note on the road, to put the reader on it.
- **Voice:** Plain, unhurried, first person plural.
- **Must include:** The road's age, the squeal of the wheel, a promise that the book is about one afternoon.
- **Must avoid:** Plot spoilers.
- **Required:** always
- **Rules:** Under 70 words.
- **Depends on:** [synopsis](../synopsis.md.wrist.md) (mentions)
- **Referred by:** none
- **Unknowns:** none
```

Create `.../salt-road/wrist/work/chapter-1.md.wrist.md`:

```markdown
# chapter: The Load

Notes for chapter 1.

- **Heading:** `# 1. The Load`
- **Point of view:** Close third on Odile, past tense.
- **Length:** About 110 words.
- **Established:** Odile carries forty sacks of salt to the sea gate. The gate closes at dusk and the tide is an hour behind her. The left wheel squeals. Pim has been hiding under the tarpaulin since the pans and gives only his name.
- **Required:** always
- **Rules:** Open on the cargo, not the weather. Odile never explains why she works alone.
- **Depends on:** none
- **Referred by:** none
- **Unknowns:** none

## scene: On the road

- **Purpose:** Establish the load, the clock and the stowaway.
- **Length:** About 110 words.
- **Must include:** Forty sacks; the squealing wheel; dusk as the deadline; the boy's head under the canvas.
- **Must avoid:** Backstory; naming a feeling.
- **Depends on:** [The load](../outline.md.wrist.md#beat-the-load) (realizes)
- **Depends on:** [Odile Marsh](../character.md.wrist.md#character-odile-marsh) (appears)
- **Depends on:** [Pim](../character.md.wrist.md#character-pim) (appears)
- **Depends on:** [The salt road](../misc.md.wrist.md#place-the-salt-road) (appears)
- **Depends on:** [The salt cart](../misc.md.wrist.md#object-the-salt-cart) (appears)
- **Depends on:** [The tide](../misc.md.wrist.md#timeline-the-tide) (mentions)
```

Create `.../salt-road/wrist/work/chapter-2.md.wrist.md`:

```markdown
# chapter: The Toll

Notes for chapter 2.

- **Heading:** `# 2. The Toll`
- **Point of view:** Close third on Odile, past tense.
- **Length:** About 130 words.
- **Established:** Brannock keeps the toll house and asks one sack in ten. Pim tells him his real name and why he came. Odile unloads all forty sacks into the road as the toll.
- **Required:** always
- **Rules:** Dialogue stays short. Brannock never raises his voice.
- **Depends on:** [The Load](./chapter-1.md.wrist.md) (continues)
- **Referred by:** none
- **Unknowns:** none

## scene: At the toll house

- **Purpose:** Put the cost of the crossing on the table and have Odile pay all of it.
- **Length:** About 130 words.
- **Must include:** The ledger; one sack in ten; Pim's one true sentence; the sacks in the road.
- **Must avoid:** A speech about generosity.
- **Depends on:** [The toll](../outline.md.wrist.md#beat-the-toll) (realizes)
- **Depends on:** [Odile Marsh](../character.md.wrist.md#character-odile-marsh) (appears)
- **Depends on:** [Pim](../character.md.wrist.md#character-pim) (appears)
- **Depends on:** [Brannock](../character.md.wrist.md#character-brannock) (appears)
- **Depends on:** [The salt cart](../misc.md.wrist.md#object-the-salt-cart) (appears)
```

Create `.../salt-road/wrist/work/chapter-3.md.wrist.md`:

```markdown
# chapter: The Gate

Notes for chapter 3.

- **Heading:** `# 3. The Gate`
- **Point of view:** Close third on Odile, past tense.
- **Length:** About 120 words.
- **Established:** The cart is empty and the wheel still squeals. Odile and Pim walk the last mile on foot beside the horse. They reach the sea gate at dusk and the keeper lets the chain run slack behind them.
- **Required:** always
- **Rules:** End on an image, not on a statement of what changed.
- **Depends on:** [The Toll](./chapter-2.md.wrist.md) (continues)
- **Referred by:** none
- **Unknowns:** none

## scene: The last mile

- **Purpose:** Resolve by action: they cross at dusk.
- **Length:** About 120 words.
- **Must include:** The empty cart; walking on either side of the horse; the chain running slack; the sea heard before it is seen.
- **Must avoid:** A closing line that states the theme.
- **Depends on:** [The gate](../outline.md.wrist.md#beat-the-gate) (realizes)
- **Depends on:** [Odile Marsh](../character.md.wrist.md#character-odile-marsh) (appears)
- **Depends on:** [Pim](../character.md.wrist.md#character-pim) (appears)
- **Depends on:** [The sea gate](../misc.md.wrist.md#place-the-sea-gate) (appears)
- **Depends on:** [The tide](../misc.md.wrist.md#timeline-the-tide) (mentions)
```

- [ ] **Step 4: Add the backlinks and check**

Run:

```bash
cd /home/sean/Data/Projects/claude-plugins/plugins/wrist/skills/wrist/assets/examples/salt-road
S=/home/sean/Data/Projects/claude-plugins/plugins/wrist/skills/wrist/scripts/wrist_check.py
python3 $S fix-backlinks wrist --write | tail -3
python3 $S check wrist | tail -6
```

Expected: `fix-backlinks` lists inserted `Referred by:` lines; `check` ends `8 stand-ins, ... 0 errors`. Warnings may remain until the realized files exist (the `Referred by:` of `synopsis` etc. are now present). If `check` reports an error or warning, fix the stand-in text and rerun until it prints `0 errors, 0 warnings`.

- [ ] **Step 5: Write the realized files**

Create `.../salt-road/synopsis.md`:

```markdown
# Salt Road: Synopsis

Odile Marsh, a salt carter, races the tide to the sea gate with forty sacks and a stowaway boy. At the toll house she pays the keeper with the whole load, and she and the boy cross on foot as the gate closes behind them.
```

Create `.../salt-road/outline.md`:

```markdown
# Salt Road: Outline

1. **The load.** Odile finds a boy under the tarpaulin and lets him ride.
2. **The toll.** She gives the toll keeper the whole load.
3. **The gate.** She walks beside the empty cart and crosses at dusk.
```

Create `.../salt-road/character.md`:

```markdown
# Salt Road: Characters

**Odile Marsh.** A salt carter who works the road alone and never asks for help. She is short and practical.

**Pim.** A boy who wants to see the sea and lies before he thinks.

**Brannock.** The toll keeper, formal and rigid, who bends once by doing nothing.
```

Create `.../salt-road/misc.md`:

```markdown
# Salt Road: Places and Things

**The salt road.** A straight road between salt pans, white on both sides, marked by milestones.

**The sea gate.** A chain gate on the shore road that closes at dusk.

**The salt cart.** A horse-drawn cart with forty sacks under a tarpaulin. Its left wheel squeals.

**The tide.** An hour behind her at the start; the gate closes at dusk.
```

Create `.../salt-road/work/forward.md`:

```markdown
# Foreword

The salt road is older than the towns at either end of it, and it has kept its name by being useful. This book is about one afternoon on it. Carters will know the squeal of the wheel and the arithmetic of the tide. Everyone else may take the road on trust.
```

Create `.../salt-road/work/chapter-1.md`:

```markdown
# 1. The Load

Forty sacks of grey salt, and the tide an hour behind her. Odile Marsh kept the horse to a walk because the left wheel squealed whenever she pushed it, and she had no oil to spare for pride.

The salt road ran straight between the pans, white on both sides, so bright at noon that she drove with her eyes half shut. Dusk was when the gate closed. Dusk did not wait for carters.

At the second milestone the tarpaulin moved. She did not stop the horse. She said, "You can come out, or you can ride with the sacks. Don't tell me which."

A boy's head came up from under the canvas, white to the eyebrows. "Pim," he said, as if she had asked.
```

Create `.../salt-road/work/chapter-2.md`:

```markdown
# 2. The Toll

Brannock kept the toll house the way other men keep a grudge: tidily, and for years. He stood in the road with his ledger open before the cart had stopped.

"One sack in ten," he said. "Forty sacks. Four."

"The tide," said Odile.

"Is in the ledger too." He looked past her. "And the boy?"

Pim opened his mouth to lie and, for once, did not. "Pim," he said. "I wanted to see the sea."

Brannock wrote it down. Then Odile climbed to the load, took her knife to the ropes, and began to push the sacks off the cart into the road, all forty, one after another, until the grey salt lay in a heap that the wind had already started to lift.

"The toll," she said, "is paid."
```

Create `.../salt-road/work/chapter-3.md`:

```markdown
# 3. The Gate

The cart ran light now and the wheel squealed anyway. Behind them Brannock stood over the salt and did not touch it.

"He'll sell it," said Pim.

"Let him." She had not looked back, and she did not now. "Walk. The horse has enough to do."

They went the last mile on foot, the boy on one side of the horse and Odile on the other, the empty cart rattling between them. The gate keeper had his hand on the chain when the first of the dusk touched the road. He saw a woman and a boy and a horse, nothing else, and he let the chain run slack.

The sea was louder than Pim had expected. He said so. Odile said it always was.
```

- [ ] **Step 6: Stamp and verify the example**

Run:

```bash
cd /home/sean/Data/Projects/claude-plugins/plugins/wrist/skills/wrist/assets/examples/salt-road
S=/home/sean/Data/Projects/claude-plugins/plugins/wrist/skills/wrist/scripts/wrist_check.py
python3 $S stamp wrist --all | tail -3
for p in generation realization publishing; do python3 $S gate wrist $p; done
python3 $S check wrist | tail -2; python3 $S status wrist | head -2; python3 $S lint wrist | head -2; python3 $S order wrist
```

Expected: `8 stamped`; three `open`; `8 stand-ins, ... 0 errors, 0 warnings`; `Realized (8):`; `0 hits in 0 files`; the order lists synopsis, outline, character, misc, forward, chapter-1, chapter-2, chapter-3. Fix the example, not the checker, if anything differs (unless it exposes a real checker bug).

- [ ] **Step 7: Add `NovelCase` to `support.py`**

In `plugins/wrist/tests/support.py`, add after the `STORY` constant line:

```python
NOVEL = os.path.join(SKILL, "assets", "examples", "salt-road")
N_PREMISE = "wrist/PREMISE.md"
N_OUTLINE = "wrist/outline.md.wrist.md"
N_CHAPTER1 = "wrist/work/chapter-1.md.wrist.md"
N_CHAPTER2 = "wrist/work/chapter-2.md.wrist.md"
N_CHAPTER3 = "wrist/work/chapter-3.md.wrist.md"
```

and replace `TreeCase.setUp`'s copy line and add the subclass at the end of the file. The class becomes:

```python
class TreeCase(unittest.TestCase):
    example = EXAMPLE

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="wrist-test-")
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        shutil.copytree(self.example, self.dir, dirs_exist_ok=True)
```

(keep the rest of `TreeCase` unchanged) and append:

```python
class NovelCase(TreeCase):
    example = NOVEL
```

- [ ] **Step 8: Write the example's tests**

Create `plugins/wrist/tests/test_novel.py`:

```python
import os
import unittest

from support import (N_CHAPTER1, N_CHAPTER2, N_CHAPTER3, N_OUTLINE, N_PREMISE, NovelCase)


class SaltRoadChecks(NovelCase):
    def test_the_example_checks_clean(self):
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("8 stand-ins", out)
        self.assertIn("0 errors, 0 warnings", out)

    def test_every_gate_is_open(self):
        for phase in ("generation", "realization", "publishing"):
            code, out = self.run_wrist("gate", "wrist", phase)
            self.assertEqual(code, 0, out)

    def test_every_file_is_realized(self):
        code, out = self.run_wrist("status", "wrist")
        self.assertIn("Realized (8):", out)

    def test_order_follows_the_profile(self):
        _, out = self.run_wrist("order", "wrist")
        names = [l.split()[1] for l in out.splitlines() if l[:1].isdigit()]
        self.assertEqual(names, ["synopsis.md", "outline.md", "character.md", "misc.md", "work/forward.md",
                                 "work/chapter-1.md", "work/chapter-2.md", "work/chapter-3.md"])

    def test_lint_is_clean(self):
        _, out = self.run_wrist("lint", "wrist")
        self.assertIn("0 hits in 0 files", out)


class SaltRoadFileSet(NovelCase):
    def test_a_fourth_chapter_needs_its_stand_in(self):
        self.replace(N_PREMISE, "chapters: 3", "chapters: 4")
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("required stand-in missing: wrist/work/chapter-4.md.wrist.md", out)

    def test_dropping_the_forward_leaves_its_stand_in_outside_the_shape(self):
        self.replace(N_PREMISE, "forward: yes", "forward: no")
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("outside the novel shape", out)

    def test_a_prologue_must_have_its_stand_in(self):
        self.replace(N_PREMISE, "prologue: no", "prologue: yes")
        code, out = self.check()
        self.assertIn("required stand-in missing: wrist/work/prologue.md.wrist.md", out)

    def test_a_missing_chapters_key_is_a_clear_error(self):
        self.replace(N_PREMISE, "chapters: 3\n", "")
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("`chapters:` is required (a whole number from 1 to 200)", out)

    def test_the_chapters_question_is_answered_by_the_front_matter(self):
        code, out = self.check()
        self.assertNotIn("question 'chapters'", out)
        self.assertNotIn("question 'forward'", out)


class SaltRoadContinuity(NovelCase):
    def test_stamp_refuses_a_chapter_with_no_established_text(self):
        self.replace(N_CHAPTER2, "- **Established:** Brannock", "- **Notes:** Brannock")
        code, out = self.run_wrist("stamp", "wrist", "work/chapter-2.md")
        self.assertEqual(code, 1, out)
        self.assertIn("no `Established:` text", out)

    def test_the_gate_blocks_a_chapter_whose_established_was_removed(self):
        text = self.read(N_CHAPTER3)
        kept = "\n".join(l for l in text.split("\n") if not l.startswith("- **Established:**"))
        self.write(N_CHAPTER3, kept)
        code, out = self.run_wrist("gate", "wrist", "publishing")
        self.assertEqual(code, 1, out)
        self.assertIn("work/chapter-3.md: its stand-in has no `Established:` text", out)

    def test_a_chapter_must_continue_the_one_before(self):
        self.replace(N_CHAPTER3, "(continues)", "(mentions)")
        code, out = self.check()
        self.assertIn("no `Depends on:` link to work/chapter-2.md's stand-in with the relation `continues`", out)

    def test_a_chapter_heading_that_drifts_blocks_publishing(self):
        self.write("work/chapter-1.md", self.read("work/chapter-1.md").replace("# 1. The Load", "# One: The Load"))
        self.run_wrist("stamp", "wrist", "work/chapter-1.md")
        code, out = self.run_wrist("gate", "wrist", "publishing")
        self.assertEqual(code, 1, out)
        self.assertIn("starts with '# One: The Load' but its stand-in's `Heading:` says '# 1. The Load'", out)

    def test_editing_a_chapter_after_stamping_blocks_publishing(self):
        self.write("work/chapter-2.md", self.read("work/chapter-2.md") + "\nA stray line.\n")
        code, out = self.run_wrist("gate", "wrist", "publishing")
        self.assertIn("work/chapter-2.md is edited", out)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 9: Run the tests and commit**

Run: `python3 -m unittest discover -s plugins/wrist/tests -q 2>&1 | tail -5`
Expected: `OK`. Fix anything the new tests expose before committing.

```bash
git add -A plugins/wrist
git commit -m "feat(wrist): add the salt-road example novel and its tests" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Publishing a book: front matter, contents and numbering

**Files:**
- Create: `plugins/wrist/skills/wrist/publish/frontmatter.lua`
- Modify: `plugins/wrist/skills/wrist/publish/book.typ`, `plugins/wrist/skills/wrist/publish/epub.css`
- Modify: `plugins/wrist/skills/wrist/scripts/wrist_publish.py` (plan flags, marker)
- Modify: `plugins/wrist/skills/wrist/scripts/wrist_check.py` (`cmd_publish`)
- Modify: `plugins/wrist/tests/test_publish.py`

**Interfaces:**
- Consumes: `Profile.expected_files`, `Profile.functions[...]["sequence"]`, `profile.title_page`; PREMISE keys `copyright`, `dedication`, `epigraph`.
- Produces in `wrist_publish`:
  - `plan_commands(inputs, meta, out_dir, slug, publish_dir)`; new `meta` keys: `front_matter: bool` (default False), `copyright`, `dedication`, `epigraph` (strings, optional). When `front_matter` is true: both commands get `--lua-filter <publish_dir>/frontmatter.lua` and a `--metadata <key>=<value>` per set key; the EPUB command gets `--toc`; the PDF command gets `-V front-matter=true` and `--metadata wrist-contents=true`.
  - `MARKER_NAME = ".wrist-body.md"`; `with_marker(sources, first_body, out_dir, cwd) -> (inputs, marker_path_or_None)` writes the marker file under `<cwd>/<out_dir>/` and inserts its relative path before `first_body`; `remove_marker(marker, cwd)`.
- `cmd_publish` passes `front_matter = True` when the profile has a `sequence` function and the file set contains a file for it, and always deletes the marker, even on failure.

- [ ] **Step 1: Write the failing tests**

In `plugins/wrist/tests/test_publish.py`, add the import `from support import NovelCase` to the existing `from support import ...` line, and add these classes before `class InstallHelp`:

```python
class BookPlan(unittest.TestCase):
    META = {"title": "Salt Road", "author": "Ada Example", "language": "en", "title_page": True}

    def plan(self, **meta):
        return dict(wrist_publish.plan_commands(["work/forward.md", "work/chapter-1.md"],
                                                dict(self.META, **meta), "output", "salt-road", PUBLISH_DIR))

    def test_a_book_without_front_matter_has_no_filter_and_no_contents_flags(self):
        plan = self.plan()
        self.assertNotIn("--lua-filter", plan["epub"] + plan["pdf"])
        self.assertNotIn("--toc", plan["epub"])
        self.assertNotIn("front-matter=true", plan["pdf"])

    def test_front_matter_adds_the_filter_the_contents_and_the_numbering_switch(self):
        plan = self.plan(front_matter=True)
        filt = os.path.join(PUBLISH_DIR, "frontmatter.lua")
        for argv in plan.values():
            self.assertEqual(argv[argv.index("--lua-filter") + 1], filt)
        self.assertIn("--toc", plan["epub"])
        self.assertIn("front-matter=true", plan["pdf"])
        self.assertIn("wrist-contents=true", plan["pdf"])
        self.assertTrue(os.path.isfile(filt))

    def test_copyright_dedication_and_epigraph_reach_both_formats(self):
        plan = self.plan(front_matter=True, copyright="(c) 2026", dedication="For X", epigraph="Q")
        for argv in plan.values():
            for item in ("copyright=(c) 2026", "dedication=For X", "epigraph=Q"):
                self.assertIn(item, argv)

    def test_review_focus_special_characters_stay_one_intact_argument(self):
        text = 'A & B #1 — "Q" café © 2026 *x* _y_'
        plan = self.plan(front_matter=True, copyright=text, dedication=text, epigraph=text)
        for argv in plan.values():
            for key in ("copyright", "dedication", "epigraph"):
                self.assertIn(f"{key}={text}", argv)

    def test_unset_front_matter_keys_are_not_passed(self):
        plan = self.plan(front_matter=True)
        self.assertFalse([a for a in plan["epub"] if a.startswith(("copyright=", "dedication=", "epigraph="))])

    def test_the_byline_filter_and_the_front_matter_filter_can_both_apply(self):
        plan = self.plan(front_matter=True, title_page=False)
        filters = [plan["epub"][i + 1] for i, a in enumerate(plan["epub"]) if a == "--lua-filter"]
        self.assertEqual(len(filters), 2)


class Marker(unittest.TestCase):
    def setUp(self):
        self.cwd = tempfile.mkdtemp(prefix="wrist-mark-")
        self.addCleanup(shutil.rmtree, self.cwd, ignore_errors=True)

    def test_the_marker_is_inserted_before_the_first_body_file(self):
        inputs, marker = wrist_publish.with_marker(["work/forward.md", "work/chapter-1.md", "work/chapter-2.md"],
                                                   "work/chapter-1.md", "output", self.cwd)
        self.assertEqual(inputs, ["work/forward.md", "output/.wrist-body.md", "work/chapter-1.md",
                                  "work/chapter-2.md"])
        self.assertEqual(marker, "output/.wrist-body.md")
        with open(os.path.join(self.cwd, marker), encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("#in-body.update(true)", text)
        self.assertIn('#set page(numbering: "1")', text)
        self.assertIn("#counter(page).update(1)", text)

    def test_no_first_body_file_means_no_marker(self):
        inputs, marker = wrist_publish.with_marker(["work/a.md"], None, "output", self.cwd)
        self.assertEqual((inputs, marker), (["work/a.md"], None))
        self.assertFalse(os.path.exists(os.path.join(self.cwd, "output")))

    def test_remove_marker_deletes_the_file_and_tolerates_none(self):
        _, marker = wrist_publish.with_marker(["c.md"], "c.md", "output", self.cwd)
        wrist_publish.remove_marker(marker, self.cwd)
        self.assertFalse(os.path.exists(os.path.join(self.cwd, marker)))
        wrist_publish.remove_marker(None, self.cwd)
        wrist_publish.remove_marker(marker, self.cwd)


class NovelBuild(NovelCase):
    @unittest.skipUnless(HAVE_TOOLS, "pandoc and typst are not installed")
    def test_the_novel_publishes_with_front_matter_and_a_contents_page(self):
        code, out = self.run_wrist("publish", "wrist")
        self.assertEqual(code, 0, out)
        with open(self.path("output/salt-road.pdf"), "rb") as fh:
            self.assertEqual(fh.read(5), b"%PDF-")
        with zipfile.ZipFile(self.path("output/salt-road.epub")) as z:
            names = z.namelist()
            opf = z.read("EPUB/content.opf").decode("utf-8")
            html = {n: z.read(n).decode("utf-8") for n in names if n.endswith(".xhtml")}
        self.assertTrue([n for n in names if "title_page" in n])
        self.assertIn('idref="nav"', opf)                                   # a visible contents page
        text = "\n".join(html.values())
        for needle in ("For the carters.", "Salt keeps what it is given.", "All rights reserved.",
                       "Foreword", "1. The Load", "2. The Toll", "3. The Gate"):
            self.assertIn(needle, text, needle)
        self.assertGreaterEqual(len([n for n in names if n.startswith("EPUB/text/ch")]), 4)   # front matter, forward, chapters
        self.assertNotIn("PREMISE", text)

    @unittest.skipUnless(HAVE_TOOLS, "pandoc and typst are not installed")
    def test_no_generated_files_are_left_behind(self):
        self.run_wrist("publish", "wrist")
        self.assertEqual(sorted(os.listdir(self.path("output"))), ["salt-road.epub", "salt-road.pdf"])

    @unittest.skipUnless(HAVE_TOOLS, "pandoc and typst are not installed")
    def test_a_failed_build_still_removes_the_marker(self):
        self.write("work/chapter-2.md", "# 2. The Toll\n\n" + "\x00" * 3 + "\n")
        self.run_wrist("stamp", "wrist", "work/chapter-2.md")
        self.run_wrist("publish", "wrist")
        self.assertFalse(os.path.exists(self.path("output/.wrist-body.md")))

    @unittest.skipUnless(HAVE_TOOLS, "pandoc and typst are not installed")
    def test_review_focus_special_characters_render(self):
        self.replace("wrist/PREMISE.md", "dedication: For the carters.", 'dedication: A & B #1 "Q" — café')
        code, out = self.run_wrist("publish", "wrist")
        self.assertEqual(code, 0, out)
        with zipfile.ZipFile(self.path("output/salt-road.epub")) as z:
            text = "\n".join(z.read(n).decode("utf-8") for n in z.namelist() if n.endswith(".xhtml"))
        self.assertIn("A &amp; B #1", text)
        self.assertIn("café", text)
```


- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m unittest discover -s plugins/wrist/tests -p test_publish.py 2>&1 | tail -4`
Expected: FAILED (the new functions and the novel publishing do not exist).

- [ ] **Step 3: Write `frontmatter.lua`**

Create `plugins/wrist/skills/wrist/publish/frontmatter.lua`:

```lua
-- Builds a book's front matter from metadata, per output format. Metadata read: copyright,
-- dedication, epigraph (text), and wrist-contents (set when a contents page is wanted in the PDF;
-- the EPUB gets its contents from pandoc's --toc).
local function text_of(meta, key)
  local v = meta[key]
  if v == nil or pandoc.utils.stringify(v) == "" then return nil end
  return pandoc.Para(pandoc.utils.blocks_to_inlines({pandoc.Plain(v)}))
end

local function page(open, para, close)
  return {pandoc.RawBlock("typst", open), para, pandoc.RawBlock("typst", close)}
end

function Pandoc(doc)
  local meta = doc.meta
  local is_typst = FORMAT:match("typst") ~= nil
  local front = {}
  local function add(blocks) for _, b in ipairs(blocks) do front[#front + 1] = b end end

  local copyright = text_of(meta, "copyright")
  if copyright then
    if is_typst then
      add(page("#pagebreak(weak: true)\n#align(bottom)[#set par(first-line-indent: 0pt)\n#text(size: 0.8em)[",
               copyright, "]]"))
    else
      add({pandoc.Div({copyright}, pandoc.Attr("", {"copyright"}))})
    end
  end
  for _, key in ipairs({"dedication", "epigraph"}) do
    local para = text_of(meta, key)
    if para then
      if is_typst then
        add(page("#pagebreak(weak: true)\n#align(center + horizon)[#set par(first-line-indent: 0pt)\n#emph[",
                 para, "]]"))
      else
        add({pandoc.Div({para}, pandoc.Attr("", {key}))})
      end
    end
  end
  if is_typst and meta["wrist-contents"] then
    add({pandoc.RawBlock("typst", "#pagebreak(weak: true)\n#outline(title: [Contents], depth: 1)")})
  end

  local out = {}
  for _, b in ipairs(front) do out[#out + 1] = b end
  for _, b in ipairs(doc.blocks) do out[#out + 1] = b end
  doc.blocks = out
  return doc
end
```

- [ ] **Step 4: Edit `book.typ` and `epub.css`**

Apply these three replacements to `plugins/wrist/skills/wrist/publish/book.typ` (each old text exists exactly once), then append the two CSS rules:

```bash
cd /home/sean/Data/Projects/claude-plugins/plugins/wrist/skills/wrist/publish && python3 - <<'PYEOF'
s = open("book.typ", encoding="utf-8").read()
def rep(old, new):
    global s
    assert old in s, old[:60]
    s = s.replace(old, new, 1)
# A book (front-matter=true) starts outside the body and the marker file switches it on at the first
# chapter. Anything else (a story, or a book with no sequence) is in the body from the start.
rep("#set document(title: [$title$])",
    '#set document(title: [$title$])\n#let in-body = state("in-body", $if(front-matter)$false$else$true$endif$)')
rep('#set page(\n  paper: "$if(papersize)$$papersize$$else$a5$endif$",\n  margin: (inside: 22mm',
    '#set page(\n  // Front matter is numbered in roman numerals; the marker switches to arabic at the first chapter.\n  numbering: "$if(front-matter)$i$else$1$endif$",\n  paper: "$if(papersize)$$papersize$$else$a5$endif$",\n  margin: (inside: 22mm')
rep("    if counter(page).get().first() > 1 {",
    "    if in-body.get() and counter(page).get().first() > 1 {")
open("book.typ", "w", encoding="utf-8").write(s)
PYEOF
cat >> epub.css <<'EOF'
.copyright p { text-align: center; font-size: 0.8em; text-indent: 0; margin: 4em 0 0; }
.dedication p, .epigraph p { text-align: center; font-style: italic; text-indent: 0; margin: 6em 1em 0; }
EOF
```

The header still hides on the first body page (the heading page of a story, or the first chapter of a book, which restarts at arabic 1) and shows from the second.

- [ ] **Step 5: Update `wrist_publish.py`**

Replace `plan_commands` and add the marker helpers in `plugins/wrist/skills/wrist/scripts/wrist_publish.py`:

```python
MARKER_NAME = ".wrist-body.md"
MARKER = ('```{=typst}\n#in-body.update(true)\n#set page(numbering: "1")\n#counter(page).update(1)\n```\n')
FRONT_KEYS = ("copyright", "dedication", "epigraph")


def plan_commands(inputs, meta, out_dir, slug, publish_dir):
    """[(kind, argv)] for the EPUB and the PDF. `meta` has title, author, optional language, trim, font,
    title_page (default True; False drops the title page and adds a byline under the first heading) and
    front_matter (default False; True adds copyright, dedication, epigraph and a contents page)."""
    common = ["pandoc", "--from", "markdown+smart", *inputs,
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
    extra = {"epub": [], "pdf": []}
    if not meta.get("title_page", True):
        # The work's own heading is its title; a byline under it replaces the title page.
        extra["epub"] += ["--epub-title-page=false", "--lua-filter", os.path.join(publish_dir, "byline.lua")]
        extra["pdf"] += ["-V", "no-title-page=true", "--lua-filter", os.path.join(publish_dir, "byline.lua")]
    if meta.get("front_matter"):
        filt = ["--lua-filter", os.path.join(publish_dir, "frontmatter.lua")]
        for key in FRONT_KEYS:
            if meta.get(key):
                filt += ["--metadata", f"{key}={meta[key]}"]
        extra["epub"] += filt + ["--toc"]
        extra["pdf"] += filt + ["-V", "front-matter=true", "--metadata", "wrist-contents=true"]
    return [("epub", epub[:-2] + extra["epub"] + epub[-2:]), ("pdf", pdf[:-2] + extra["pdf"] + pdf[-2:])]


def with_marker(sources, first_body, out_dir, cwd):
    """The pandoc inputs with a marker file before the first body file, so the PDF switches from roman
    to arabic page numbers there. Returns (inputs, marker path or None)."""
    if first_body is None or first_body not in sources:
        return list(sources), None
    os.makedirs(os.path.join(cwd, out_dir), exist_ok=True)
    marker = f"{out_dir}/{MARKER_NAME}"
    with open(os.path.join(cwd, marker), "w", encoding="utf-8") as fh:
        fh.write(MARKER)
    inputs = list(sources)
    inputs.insert(inputs.index(first_body), marker)
    return inputs, marker


def remove_marker(marker, cwd):
    if marker:
        try:
            os.remove(os.path.join(cwd, marker))
        except FileNotFoundError:
            pass
```

(Keep `missing_tools`, `install_help`, `PublishError` and `run_commands` as they are, and delete the previous `plan_commands` definition. The earlier title-page tests still pass: with `front_matter` unset the result is identical to before.)

- [ ] **Step 6: Update `cmd_publish`**

In `wrist_check.py`, replace the body of `cmd_publish` from `wrist_root, files, profile, pm, slug = load_all(args)` down to the final `return 0` with:

```python
    wrist_root, files, profile, pm, slug = load_all(args)
    root = project_root(args)
    expected = profile.expected_files(slug)
    sources = [path for path, function in expected if profile.functions[function]["prose"]]
    first_body = next((path for path, function in expected if profile.functions[function]["sequence"]), None)
    meta = {"title": pm.front["title"][1], "author": pm.front["author"][1],
            "language": pm.front.get("language", (0, "en"))[1], "trim": pm.front.get("trim", (0, ""))[1],
            "font": pm.front.get("font", (0, ""))[1], "title_page": profile.title_page,
            "front_matter": first_body is not None}
    for key in wrist_publish.FRONT_KEYS:
        meta[key] = pm.front.get(key, (0, ""))[1]
    inputs, marker = wrist_publish.with_marker(sources, first_body, "output", root)
    try:
        wrist_publish.run_commands(wrist_publish.plan_commands(inputs, meta, "output", slug, PUBLISH_DIR), root)
    except wrist_publish.PublishError as exc:
        print(f"publish failed: {exc}")
        return 1
    finally:
        wrist_publish.remove_marker(marker, root)
    print(f"published output/{slug}.epub and output/{slug}.pdf")
    return 0
```

- [ ] **Step 7: Run the tests, then look at the PDF**

Run: `python3 -m unittest discover -s plugins/wrist/tests -q 2>&1 | tail -6`
Expected: `OK` (the real-build tests run because pandoc and typst are installed). If `test_the_novel_publishes...` fails on a needle, print the EPUB text and decide whether the test or the filter is wrong.

Then build the example and look at it (a PDF reader is not installed; use a scratch virtualenv):

```bash
S=/tmp/claude-1000/-home-sean-Data-Projects-claude-plugins/b823c3ae-57a6-454b-b3b3-63ef3fa1a7f8/scratchpad
rm -rf $S/novel-out && cp -r /home/sean/Data/Projects/claude-plugins/plugins/wrist/skills/wrist/assets/examples/salt-road $S/novel-out
cd $S/novel-out && python3 /home/sean/Data/Projects/claude-plugins/plugins/wrist/skills/wrist/scripts/wrist_check.py publish wrist
[ -d $S/venv ] || (python3 -m venv $S/venv && $S/venv/bin/pip install -q pymupdf)
$S/venv/bin/python - <<'EOF'
import pymupdf
d = pymupdf.open("output/salt-road.pdf"); print(len(d), "pages")
w, h = d[0].rect.width * 0.5, d[0].rect.height * 0.5
sheet = pymupdf.open(); page = sheet.new_page(width=w * len(d), height=h)
for i in range(len(d)): page.show_pdf_page(pymupdf.Rect(i * w, 0, (i + 1) * w, h), d, i)
page.get_pixmap(dpi=100).save("output/sheet.png")
EOF
```

Open `output/sheet.png` and confirm: a title page; copyright at the foot of its own page; the dedication and epigraph centered on their own pages; a contents page listing Foreword and the three chapters; roman page numbers through the Foreword; the first chapter numbered 1 with a running head from the second chapter page on. Fix `frontmatter.lua` or `book.typ` for anything that is wrong, then rerun the suite.

- [ ] **Step 8: Commit**

```bash
git add -A plugins/wrist
git commit -m "feat(wrist): publish a book with front matter, a contents page and roman then arabic numbering" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Skill, references and novel templates

**Files:**
- Modify: `plugins/wrist/skills/wrist/SKILL.md`, `references/grammar.md`, `references/publishing.md`
- Create: `plugins/wrist/skills/wrist/assets/templates/novel/` with `PREMISE.md`, `synopsis.wrist.md`, `outline.wrist.md`, `characters.wrist.md`, `misc.wrist.md`, `forward.wrist.md`, `chapter.wrist.md`, `afterward.wrist.md`, `index.wrist.md`
- Modify: `README.md` (the wrist section), `plugins/wrist/.claude-plugin/plugin.json` (description), `plugins/wrist/tests/test_docs.py`

**Interfaces:**
- Consumes: question ids and keys from Task 3; commands and messages from Task 2; publishing behavior from Task 5.
- Produces: `SKILL.md` that asks which profile (short story or novel), names the premise keys, the per-chapter realization loop (`Established:` then stamp), and where the templates are.

- [ ] **Step 1: Write the failing docs tests**

In `plugins/wrist/tests/test_docs.py`, add to `SkillText`:

```python
    def test_skill_covers_the_novel(self):
        skill = text(SKILL, "SKILL.md")
        for phrase in ("`novel`", "chapters:", "Established:", "assets/templates/novel/",
                       "realize the chapter, fill in `Established:`, stamp it"):
            self.assertIn(phrase, skill, phrase)

    def test_every_novel_template_exists(self):
        for name in ("PREMISE.md", "synopsis.wrist.md", "outline.wrist.md", "characters.wrist.md", "misc.wrist.md",
                     "forward.wrist.md", "chapter.wrist.md", "afterward.wrist.md", "index.wrist.md"):
            self.assertTrue(os.path.isfile(os.path.join(SKILL, "assets", "templates", "novel", name)), name)

    def test_the_grammar_reference_explains_the_new_profile_features(self):
        grammar = text(SKILL, "references", "grammar.md")
        for phrase in ("premise_keys", "family", "when", "Established", "continues", "Heading"):
            self.assertIn(phrase, grammar, phrase)

    def test_the_readme_lists_the_novel(self):
        readme = text(ROOT, "README.md")
        self.assertIn("`shortstory` and `novel`", readme)
```

Run: `python3 -m unittest discover -s plugins/wrist/tests -p test_docs.py 2>&1 | tail -4` — expect FAILED.

- [ ] **Step 2: Write the novel templates**

Create the nine files under `plugins/wrist/skills/wrist/assets/templates/novel/`.

`PREMISE.md`:

```markdown
---
profile: novel
title: <Title>
slug: <lower-case-words-joined-by-hyphens>
author: <Author name>
language: en
chapters: <whole number, 1 to 200>
forward: <yes or no>
prologue: <yes or no>
afterward: <yes or no>
index: <yes or no>
---

# Premise

<One or two sentences: what this book is.>

## Answers

- **genre:** <answer>
- **premise:** <answer>
- **ending:** <answer>
- **tone:** <answer>
- **audience:** <answer>
- **length:** <answer>
- **viewpoint:** <answer>
- **subgenre:** <answer, or none (skipped on purpose)>
- **themes:** <answer>
- **comps:** <answer>
- **series:** <answer>
- **setting:** <answer>
- **worldrules:** <answer>
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
- **Rules:** <length, tense, voice; must state the ending>
- **Required:** always
- **Depends on:** none
- **Unknowns:** none
```

`outline.wrist.md`:

```markdown
# outline: <Title>

<What the outline must do.>

- **Structure:** <chosen structure from structures.md, or *UNKNOWN*: with Proposed:>
- **Rules:** <how many beats, which chapters each beat covers, what each must change>
- **Required:** always
- **Depends on:** [synopsis](./synopsis.md.wrist.md) (mentions)
- **Unknowns:** none

## beat: <Beat name>

- **Purpose:** <what this beat is for>
- **Change:** <what is different after it>
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

- **Wants:** <what they want in this book>
- **Flaw:** <what stands in their way>
- **Voice:** <how they speak>
- **Arc:** <where they start and where they end>
```

`misc.wrist.md`:

```markdown
# misc: <Title>

<What this file holds: places, objects, concepts and the timeline.>

- **Rules:** <what may and may not be named>
- **Required:** always
- **Depends on:** [synopsis](./synopsis.md.wrist.md) (mentions)
- **Unknowns:** none

## place: <Name>

- **Facts:** <fixed facts the text must respect>

## timeline: <Name>

- **Facts:** <dates, durations and the order of events the text must respect>
```

`forward.wrist.md` (the prologue and afterward stand-ins use the same fields; change `forward` to `prologue` or `afterward` in the heading, and the `Heading:` line to the printed heading):

```markdown
# forward: <Title>

<What this part must do.>

- **Heading:** `# Foreword`
- **Purpose:** <why the book needs it>
- **Voice:** <who speaks and how>
- **Must include:** <what must appear>
- **Must avoid:** <spoilers and what must not appear>
- **Required:** always
- **Rules:** <length and constraints>
- **Depends on:** [synopsis](../synopsis.md.wrist.md) (mentions)
- **Referred by:** none
- **Unknowns:** none
```

`chapter.wrist.md` (copy once per chapter, named `chapter-<n>.md.wrist.md` with `<n>` zero-padded to the width of the chapter count):

```markdown
# chapter: <Chapter name>

<What this chapter must do.>

- **Heading:** `# <n>. <Chapter name>`
- **Point of view:** <person, whose, tense>
- **Length:** <target words>
- **Established:** <left empty until the chapter is realized; then every new fact, date, injury, object moved, who knows what and promise the text fixed>
- **Required:** always
- **Rules:** <voice, forbidden moves, quality rules copied from quality.md>
- **Depends on:** [<Previous chapter>](./chapter-<n-1>.md.wrist.md) (continues)
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

`afterward.wrist.md`:

```markdown
# afterward: <Title>

<What this part must do.>

- **Heading:** `# Afterword`
- **Purpose:** <why the book needs it>
- **Voice:** <who speaks and how>
- **Must include:** <what must appear>
- **Must avoid:** <what must not appear>
- **Required:** always
- **Rules:** <length and constraints>
- **Depends on:** [synopsis](../synopsis.md.wrist.md) (mentions)
- **Referred by:** none
- **Unknowns:** none
```

`index.wrist.md`:

```markdown
# index: <Title>

<What the index must hold.>

- **Heading:** `# Index`
- **Required:** always
- **Rules:** <what is indexed (names, places, concepts), how entries are ordered, how references are given>
- **Depends on:** [characters](../character.md.wrist.md) (mentions)
- **Referred by:** none
- **Unknowns:** none
```

- [ ] **Step 3: Edit `SKILL.md`**

Apply these replacements to `plugins/wrist/skills/wrist/SKILL.md` (assert each anchor exists; read the file first and adjust a whitespace difference rather than skipping the edit):

1. Replace the sentence `Only the `shortstory` profile exists so far; if the user wants a novel, screenplay or poem, say it is not built yet.` with:
   `Two profiles exist: `shortstory` and `novel`. If the user wants a screenplay or a poem, say it is not built yet. Each profile has its own folder under `profiles/` (questions, structures, quality lists) and its own templates: `assets/templates/` for the short story and `assets/templates/novel/` for the novel.`
2. In Premise step 1, replace `Ask which profile (`shortstory`). Read `profiles/shortstory/questions.md`.` with:
   `Ask which profile (`shortstory` or `novel`) and read `profiles/<profile>/questions.md`.`
3. At the end of Premise step 3, add: `For a novel the front matter also holds the keys that decide which files exist: `chapters:` (a whole number; if the user is unsure, propose one from the length and the structure, then fix it), and `forward:`, `prologue:`, `afterward:`, `index:` (each `yes` or `no`). Ask each of the four with the reason it is wanted. These answers count for their questions, so they need no line in the body. Changing one later means changing the tree. Optional front matter text for the published book (`copyright:`, `dedication:`, `epigraph:`) is asked in the publishing question phase.`
4. In Generation step 3, replace `using `assets/templates/`` with `using `assets/templates/` (short story) or `assets/templates/novel/` (novel)`, and add this sentence after it: `For a novel write one chapter stand-in per chapter, named with the number zero-padded to the width of the chapter count (`chapter-07.md.wrist.md` in a 28-chapter book), with a `(continues)` link to the chapter before, a `Heading:` line giving the exact first line of the realized file, and `Established:` left empty.`
5. In Realization step 2, add after the sentence about stamping: `For a novel, do this one chapter at a time: realize the chapter, fill in `Established:` in its stand-in with every new fact, date, injury, object moved, who-knows-what and promise the text fixed, then stamp it. `stamp` refuses a chapter whose `Established:` is empty. Before writing a chapter, read the `Established:` fields of the chapters before it (and the registries) instead of rereading their text.`
6. In Publishing step 1, add: `For a novel also ask for the copyright line, the dedication and the epigraph (each optional, one line), and put them in `PREMISE.md` as `copyright:`, `dedication:` and `epigraph:`.`
7. Make sure the exact phrase `realize the chapter, fill in `Established:`, stamp it` appears (adjust the wording in edit 5 if needed so the docs test finds it verbatim).

- [ ] **Step 4: Edit the references, README and manifest**

Append to `plugins/wrist/skills/wrist/references/grammar.md`:

```markdown
## 7. What a profile can add

A profile (`profiles/<name>/profile.json`) decides the file shape and what every stand-in must hold. Beyond the short story's fixed files it can declare:

- **`premise_keys`**: the `PREMISE.md` front matter keys it reads, each `bool` (`yes` or `no`, default no) or `int` (a whole number within `min` and `max`, optionally `required`). A wrong or missing required value is a `check` error that names the key. A question whose id is a premise key counts as answered when the front matter has the key.
- **`when`** on a file entry: the file exists only when that bool key is yes (`forward: yes` makes `work/forward.md`).
- **`family`** on a file entry: the file expands into one per number from 1 to the int key's value, with `{n}` in the path replaced by the number zero-padded to the width of the count. `check` requires exactly those stand-ins, so changing the count means changing the tree.
- **`required_when_realized`**: fields a stand-in must hold once its realized file exists. For a novel chapter this is `Established:`; `stamp` refuses a chapter without it and `gate publishing` reports it. Text on the same line, or on the lines that follow it up to a blank line, counts; an empty field does not.
- **`sequence`**: each file of a family should link to the one before it with the relation `continues`; `check` warns when it does not.
- **`heading_field`**: the field (for the novel, `Heading:`) whose value is the exact first line of the realized file, for example `# 7. The Long Wait`. `gate publishing` reports a realized file that starts with something else.
- **`title_page`**: whether the published book has a separate title page (default true; the short story sets it false).
```

In `references/publishing.md`, add before `## When the build fails`:

```markdown
## A book with front matter

When a profile has a `sequence` function (a novel's chapters), the book is assembled in this order: title page, copyright page, dedication, epigraph, contents, then the realized files in the profile's order. The copyright, dedication and epigraph are the `copyright:`, `dedication:` and `epigraph:` keys of `PREMISE.md`, each optional; the contents page is generated from the level-1 headings. In the PDF every page before the first chapter carries no running head and is numbered in lower-case roman numerals after the title page; the first chapter's page is arabic 1. In the EPUB the contents page is the navigation document, listed in the reading order after the title page. The publisher writes a temporary marker file into `output/` for the numbering switch and removes it afterward.
```

In `README.md`, in the wrist section, change the sentence that says only `shortstory` exists so that it reads "`shortstory` and `novel` exist; screenplay and poem profiles are planned." (read the section and edit the wrapped lines in place). In `plugins/wrist/.claude-plugin/plugin.json` change the description's last sentence from `Starts with the short story profile` to `Profiles: short story and novel`.

- [ ] **Step 5: Run the tests and commit**

Run: `python3 -m unittest discover -s plugins/wrist/tests -q 2>&1 | tail -4`
Expected: `OK`.

```bash
git add -A plugins/wrist README.md
git commit -m "docs(wrist): teach the skill and references the novel profile" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Trial: a fresh session writes a short novel

This task is performed by the executor, not by a test. The short story trial found five defects the 223-test suite could not, so this is required for the cycle to be called done.

**Files:**
- Create: `notes/wrist-novel-trial.md` (untracked notes, like `notes/wrist-trial.md`)
- Modify: whatever the trial exposes (plugin files), with a failing test first for each code defect

**Interfaces:**
- Consumes: everything above.
- Produces: a written account of what worked and what did not, fixes committed, and the PDF and EPUB looked at.

- [ ] **Step 1: Set up the harness**

```bash
S=/tmp/claude-1000/-home-sean-Data-Projects-claude-plugins/b823c3ae-57a6-454b-b3b3-63ef3fa1a7f8/scratchpad
rm -rf $S/ntrial && mkdir -p $S/ntrial && cd $S/ntrial && git init -q .
cat > $S/nturn.sh <<'EOF'
#!/usr/bin/env bash
# usage: nturn.sh N "message" [session-id]
S=/tmp/claude-1000/-home-sean-Data-Projects-claude-plugins/b823c3ae-57a6-454b-b3b3-63ef3fa1a7f8/scratchpad
cd $S/ntrial
ARGS=(-p "$2" --plugin-dir /home/sean/Data/Projects/claude-plugins/plugins/wrist --model sonnet --output-format json
      --permission-mode acceptEdits --allowedTools "Bash Read Write Edit Glob Grep Skill" --max-budget-usd 12)
[ -n "$3" ] && ARGS+=(--resume "$3")
claude "${ARGS[@]}" > $S/nturn-$1.json 2> $S/nturn-$1.err
python3 - "$1" <<'PY'
import json, sys
S = "/tmp/claude-1000/-home-sean-Data-Projects-claude-plugins/b823c3ae-57a6-454b-b3b3-63ef3fa1a7f8/scratchpad"
d = json.load(open(f"{S}/nturn-{sys.argv[1]}.json"))
print("session:", d.get("session_id")); print("cost:", d.get("total_cost_usd"), "turns:", d.get("num_turns"), "dur_s:", round(d.get("duration_ms", 0) / 1000))
print("----"); print(d.get("result", ""))
PY
EOF
chmod +x $S/nturn.sh
```

- [ ] **Step 2: Run the conversation**

Use five to eight resumed turns, playing the author, with a premise different from the short story and from the example: a three-chapter novella-sized "novel" (a short book, about 3 chapters of 300 to 500 words, to keep the cost low), genre quiet science fiction, a forward and an afterward wanted, no prologue or index, an epigraph and dedication. Leave the structure to the agent and skip one deferrable question on purpose. Turn 1: "I'd like to write a novel." Then answer its questions; accept its proposals; ask it to continue through generation, realization (one chapter at a time) and publishing. Capture each turn's cost and result.

- [ ] **Step 3: Inspect the output yourself**

Read every stand-in and the realized text. Run `check`, `status`, `lint` and all three gates with the plugin's scripts. Look at the PDF pages (the scratch virtualenv from Task 5) and open the EPUB structure. Compare the story and the stand-ins as the author: did the agent fill `Established:` honestly, record its own choices as unknowns, add facts the stand-ins do not hold, keep the chapter count?

- [ ] **Step 4: Fix and record**

For each defect: a failing test first for a code defect, the smallest fix, the suite green, a commit. Guidance defects go into `SKILL.md` with a test pinning the phrase. Write the findings in `notes/wrist-novel-trial.md` with each marked `[observed]` or `[not verified]`, and what was fixed versus left. Do not report a finding as a mistake until you have checked it against the stand-ins and the premise.

- [ ] **Step 5: Commit**

```bash
git add -A plugins/wrist
git commit -m "fix(wrist): close the defects the novel trial exposed" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

(Skip if the trial exposed nothing to fix, and say so.)

---

### Task 8: Whole-plugin verification

**Files:**
- Modify: `docs/superpowers/specs/2026-10-03-wrist-novel-design.md` if the build departed from it

- [ ] **Step 1: Full suite, both profiles**

Run: `python3 -m unittest discover -s plugins/wrist/tests -v 2>&1 | tail -6; python3 -m unittest discover -s plugins/skel/tests -q 2>&1 | tail -3`
Expected: wrist `OK` with no skips (pandoc and typst are installed); skel `OK` (223 tests), unchanged.

- [ ] **Step 2: Both examples as a user**

```bash
cd /home/sean/Data/Projects/claude-plugins/plugins/wrist/skills/wrist/assets/examples
S=../../../scripts/wrist_check.py
for e in the-lamp salt-road; do (cd $e && echo "== $e" && python3 $S check wrist | tail -1 && python3 $S status wrist | head -1 && python3 $S lint wrist | head -1 && for p in generation realization publishing; do python3 $S gate wrist $p; done); done
```

Expected: both `0 errors, 0 warnings`, every file realized, 0 lint hits, all six gates open. Do not leave an `output/` folder in either example.

- [ ] **Step 3: Leftover scan**

Run: `grep -rniE "skel|TODO|TBD|FIXME" plugins/wrist -I | grep -vi 'skelet' | grep -v 'tests/'`
Expected: only the legitimate informal-marker regex and the `todo` variable names in `wrist_check.py` and the grammar's description of informal markers.

- [ ] **Step 4: Bring the spec in line**

Edit the novel spec where the build differs (for example: the Lua filter and marker mechanism replaced a generated front-matter file; premise binding through `Profile.set_premise` instead of passing options to every call; `title_page` handling; `field_text` accepting following lines). Add each as a numbered line under "Open decisions" and commit with the final fixes.

- [ ] **Step 5: Commit**

```bash
git add -A docs plugins/wrist
git commit -m "docs(wrist): bring the novel spec in line with the build" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

## Self-review

**1. Spec coverage**

| Spec section | Task |
|---|---|
| Decisions: file set in `PREMISE.md`; `Established:`; front matter keys; title page | 1, 2, 4, 5 |
| `files` kinds `when`, `family`; zero padding; order | 1 |
| `premise_keys` (types, bounds, errors, undeclared ignored) | 1, 2 |
| API: `expected_files`, `function_for`, `resolve_options` | 1 (premise bound once in `load_all`, Task 2) |
| `required_when_realized`, `sequence`, `heading_field`, `continues` | 1, 2, 3 |
| `stamp` refusal; gate blockers; `(continues)` warning | 2 |
| Novel file shape, functions, relations, limits | 3 |
| Established semantics (same line or following lines; empty fails) | 2 |
| Premise keys incl. optional text keys | 3, 5, 6 |
| Structures, questions, quality data, `lint.json` | 3 |
| Publishing order, front matter mechanism, PDF numbering, EPUB contents, gate | 2, 5 |
| Skill and documentation | 6 |
| Example, engine tests, profile tests, publish tests | 1 to 5 |
| Trial required for done | 7 |
| Out of scope (screenplay, poem, parts, index generation, series, covers) | not built |
| Open decisions 1 to 7 | built as written; 8 added by Task 8 step 4 |

Departures from the spec, to record in Task 8: the premise is bound to the profile once (`Profile.set_premise`) instead of every caller passing options (same behavior, far fewer edits); front matter is built by a Lua filter and a marker file rather than a generated front-matter markdown file (a prototype showed the generated-file route renders text in both formats and misparses `(c)` as a list).

**2. Placeholder scan:** the only deliberate instruction-level placeholders are the `<...>` slots inside template files (Task 6) and the described-but-not-scripted conversation in Task 7, which is a manual trial. Task 3 step 1 contains a no-op test line that the step itself says to replace before running; fix it when writing the test, not after.

**3. Type consistency:** `Profile.set_premise(front: dict[str, str])`, `option_problems: list[(key, message)]`, `expected_files(slug, options=None)`, `function_for(rel, slug, options=None)` and `sequence_prev(slug, options=None)` are used with those signatures in `wrist_check.py` (Task 2) and the tests. `field_text(sf, sec, label)`, `missing_when_realized(sf, profile, slug) -> list[str]` and `heading_problem(sf, profile, slug, impl) -> str | None` are defined in Task 2 and used by `stamp` and `gate` there. `plan_commands(inputs, meta, out_dir, slug, publish_dir)`, `with_marker(sources, first_body, out_dir, cwd)` and `remove_marker(marker, cwd)` match between Task 5's code and tests. Question ids and premise keys match between `profile.json`, `questions.md`, the example's `PREMISE.md` and the tests.

**4. Review Focus coverage:** items 1 to 4 are `test_review_focus_*` cases in `CheckEngine` (Task 2); item 5 is `test_review_focus_special_characters_*` in `BookPlan` and `NovelBuild` (Task 5).

**Known risks the executor should watch:**
- Task 2 edits `wrist_check.py` by anchor strings; the script asserts each exists, so read any assertion failure as a drifted anchor, not a reason to skip the edit.
- The example's `check` must reach `0 errors, 0 warnings`; most failures there are example text (prose limit, a missing backlink), fixed in the example.
- `book.typ` behavior (running heads, numbering) is verified only by looking at the PDF; Task 5 step 7 is not optional.
- The Task 7 trial costs money and time (the short story trial cost $1.53); the `--max-budget-usd 12` cap is deliberately generous.
