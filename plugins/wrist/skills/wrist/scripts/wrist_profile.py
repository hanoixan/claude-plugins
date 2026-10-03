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
