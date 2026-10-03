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
OPTIONAL_KEYS = {"title_page"}      # title_page: a separate title page when published; default true
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
    extra = sorted(set(data) - TOP_KEYS - OPTIONAL_KEYS)
    if extra:
        raise ProfileError(f"profile.json has unknown key {extra[0]!r}")
    if not isinstance(data.get("title_page", True), bool):
        raise ProfileError("'title_page' must be true or false")
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
        self.title_page = data.get("title_page", True)
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
