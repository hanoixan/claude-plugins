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
import unicodedata
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wrist_lint
import wrist_profile
import wrist_publish

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


def slugify(text):
    s = text.strip().lower()
    s = re.sub(r"[^\w\- ]", "", s)
    return s.replace(" ", "-")


class Section:
    def __init__(self, level, kind, name, title, line, parent=None):
        self.level, self.kind, self.name, self.title, self.line = level, kind, name, title, line
        self.parent = parent
        self.fields = defaultdict(list)   # label -> [(line, value)]
        self.links = []                   # field links
        self.any_links = 0                # any markdown link in prose
        self.fences = 0
        self.children = []

    def typed_owner(self):
        s = self
        while s is not None and s.kind is None:
            s = s.parent
        return s

    def qualified(self):
        """Dotted name of typed ancestors; the level-1 name is used only for level-1 itself."""
        if self.level == 1:
            return self.name
        parts, s = [], self
        while s is not None and s.level > 1:
            if s.kind:
                parts.append(s.name)
            s = s.parent
        return ".".join(reversed(parts)) or self.name


class Link:
    def __init__(self, label, text, target, line, section, relation=None):
        self.label, self.text, self.target, self.line, self.section = label, text, target, line, section
        self.relation = relation


def front_matter_end(lines):
    """Index of the `---` that closes the front matter, 0 if the file has none, -1 if one opens
    with `---` and is not closed before the first line that is not `key: value` or blank."""
    if not lines or lines[0].strip() != "---":
        return 0
    for j in range(1, len(lines)):
        if lines[j].strip() == "---":
            return j
        if lines[j].strip() and not META_RE.match(lines[j]):
            break
    return -1


def meta_value(raw):
    """A front matter value as written. Quotes are dropped only when one pair wraps the whole value,
    and `#` is ordinary text: a title like `Room #9` must reach the publisher intact."""
    value = raw.strip()
    if len(value) > 1 and value[0] == value[-1] and value[0] in "\"'" and value[0] not in value[1:-1]:
        value = value[1:-1].strip()
    return value


def read_text(path, encoding="utf-8"):
    try:
        with open(path, encoding=encoding) as fh:
            return fh.read()
    except (OSError, UnicodeDecodeError) as exc:
        sys.exit(f"{path}: cannot read ({exc})")


class Unknown:
    """One *UNKNOWN* marker: a declaration, or a follower of a named declaration."""

    def __init__(self, line, text, section=None):
        self.line, self.text, self.section = line, text, section
        self.name = self.follows = self.bad_name = None
        body = text
        m = FOLLOWS_RE.match(body)
        if m:
            self.follows = m.group(1)
        else:
            m = BRACKET_RE.match(body)
            if m:
                self.name = m.group(1)
        if m:
            body = body[m.end():]
            if not NAME_RE.match(m.group(1)):
                self.bad_name, self.name = m.group(1), None
        parts = CLAUSE_RE.split(body)
        self.clauses = {}
        for label, value in zip(parts[1::2], parts[2::2]):
            if value.strip(" ."):                      # a label with nothing after it states nothing
                self.clauses.setdefault(label.lower(), value.strip())

    @property
    def kind(self):
        return self.clauses.get("kind", "").strip(" .`*_").lower()

    @property
    def where(self):
        return heading_path(self.section) if self.section is not None else "(premise)"

    @property
    def label(self):
        """`where` as printed inside brackets in text output."""
        return heading_path(self.section) if self.section is not None else "premise"


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


def parse(path, wrist_root):
    sf = WristFile(path, wrist_root)
    sf.lines = read_text(path, "utf-8-sig").split("\n")    # a byte-order mark is not content
    lines = sf.lines
    start = 0
    end = front_matter_end(lines)
    if end == -1 and len(lines) > 1 and META_RE.match(lines[1]):
        sf.err(1, "front matter is not closed with `---`")
    if end > 0:
        start = end + 1
        sf.warn(1, "stand-ins take no front matter; the profile decides what each file is")

    stack = [sf.root]
    cur = sf.root
    fence = None
    pending = None  # label awaiting block-form links
    for idx in range(start, len(lines)):
        line, ln = lines[idx], idx + 1
        fm = FENCE_RE.match(line)
        if fence:
            if fm and fm.group(1)[0] == fence[0] and len(fm.group(1)) >= len(fence) and not fm.group(2).strip():
                fence = None
            continue
        if fm:
            fence = fm.group(1)
            if not fm.group(2).strip():
                sf.err(ln, "code fence has no language tag (use ```text for plain text)")
            cur.fences += 1
            pending = None
            continue
        hm = HEADING_RE.match(line)
        if hm:
            level, title = len(hm.group(1)), hm.group(2)
            tm = TYPED_RE.match(title)
            kind = tm.group(1).lower() if tm else None
            name = tm.group(2).strip() if tm else title
            while stack[-1].level >= level:
                stack.pop()
            sec = Section(level, kind, name, title, ln, stack[-1])
            stack[-1].children.append(sec)
            stack.append(sec)
            sf.sections.append(sec)
            cur = sec
            pending = None
            continue
        cur.any_links += len(LINK_RE.findall(line))
        fld = FIELD_RE.match(line)
        if fld:
            label, value = CANON[fld.group(1).lower()], fld.group(2)
            cur.fields[label].append((ln, value))
            pending = None
            if label in ("Depends on", "Referred by"):
                found = LINK_REL_RE.findall(value)
                for text, target, rel in found:
                    cur.links.append(Link(label, text, target, ln, cur, rel or None))
                if not found:
                    if value.strip() == "":
                        pending = (label, ln)
                    elif not NONE_RE.match(value) and not UNKNOWN_RE.search(value):
                        sf.err(ln, f"`{label}:` has no markdown link; use [symbol](path) or 'none'")
        elif pending and BULLET_LINK_RE.match(line):
            for text, target, rel in LINK_REL_RE.findall(line):
                cur.links.append(Link(pending[0], text, target, ln, cur, rel or None))
        elif pending and line.strip():
            if not cur.links or cur.links[-1].line < pending[1]:
                sf.err(pending[1], f"`{pending[0]}:` is empty and not followed by bulleted links")
            pending = None
        um = UNKNOWN_RE.search(line)
        if um:
            sf.unknowns.append(Unknown(ln, um.group(1).strip(), cur))
        elif INFORMAL_RE.search(line):
            sf.warn(ln, f"informal marker '{INFORMAL_RE.search(line).group(1)}'; use *UNKNOWN*: ...")
    if pending and (not cur.links or cur.links[-1].line < pending[1]):
        sf.err(pending[1], f"`{pending[0]}:` is empty and not followed by bulleted links")
    if fence:
        sf.err(len(lines), "unclosed code fence")
    return sf


def own_fields(sec):
    """Fields of a typed section plus its untyped descendants (stopping at typed ones)."""
    agg = defaultdict(list)
    todo = [sec]
    while todo:
        s = todo.pop()
        for k, v in s.fields.items():
            agg[k].extend(v)
        todo.extend(c for c in s.children if c.kind is None)
    return agg


def own_count(sec, attr):
    total, todo = 0, [sec]
    while todo:
        s = todo.pop()
        total += getattr(s, attr)
        todo.extend(c for c in s.children if c.kind is None)
    return total


def file_fields(sf):
    agg = defaultdict(list)
    for s in [sf.root] + sf.sections:
        for k, v in s.fields.items():
            agg[k].extend(v)
    return agg


def find_untyped(sf, title):
    return [s for s in sf.sections if s.kind is None and s.title.strip().lower() == title.lower()]


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


def relpath_dot(target, start_dir):
    rel = os.path.relpath(target, start_dir)
    return rel if rel.startswith(".") else "./" + rel


def resolve(sf, target):
    path, _, frag = target.partition("#")
    if path == "":
        return sf.path, frag
    return os.path.normpath(os.path.join(os.path.dirname(sf.path), path)), frag


def fragment_problems(text, frag, target, where):
    """(severity, message) pairs for a link's #fragment against the headings of the file it targets."""
    secs = [s for s in target.sections if slugify(s.title) == frag]
    if not secs:
        return [("error", f"fragment '#{frag}' does not match any heading in {where}")]
    dotted = DOTTED_RE.match(text.strip())
    symbols = [s for s in secs if s.level > 1 and s.kind]
    if dotted and symbols:
        module = next((s.name for s in target.sections if s.level == 1), "")
        names = {s.qualified() for s in symbols}
        if dotted.group(1) not in names | {f"{module}.{n}" for n in names}:
            return [("warning", f"link text '{dotted.group(1)}' does not match the heading it points at "
                                f"({', '.join(sorted(names))})")]
    return []


def build_edges(wrist_root, files, report=True):
    deps = defaultdict(list)   # (A,B) -> [Link]   A depends on B
    refs = defaultdict(list)   # (B,A) -> [Link]   B says it is referred by A
    for sf in files.values():
        for lk in sf.all_links():
            if EXTERNAL_RE.match(lk.target):
                if lk.label == "Referred by" and report:
                    sf.err(lk.line, "`Referred by:` must point at a .wrist.md file, not a URL")
                continue
            tgt, frag = resolve(sf, lk.target)
            if tgt == sf.path:
                if frag and report:
                    for sev, msg in fragment_problems(lk.text, frag, sf, "this file"):
                        sf.diags.append((sev, lk.line, msg))
                continue
            if not os.path.exists(tgt):
                if report:
                    sf.err(lk.line, f"link target does not exist: {lk.target}")
                continue
            inside = os.path.commonpath([tgt, wrist_root]) == wrist_root
            if tgt not in files:
                if report:
                    if lk.label == "Referred by":
                        sf.err(lk.line, "`Referred by:` must point at a .wrist.md file")
                    elif inside:
                        sf.warn(lk.line, "dependency inside wrist/ should target a .wrist.md stand-in")
                continue
            if frag and report:
                for sev, msg in fragment_problems(lk.text, frag, files[tgt], lk.target.split("#")[0]):
                    sf.diags.append((sev, lk.line, msg))
            if lk.label == "Depends on":
                deps[(sf.path, tgt)].append(lk)
            else:
                refs[(sf.path, tgt)].append(lk)
    return deps, refs


def check_bidirectional(files, deps, refs):
    for (a, b), lks in deps.items():
        if (b, a) not in refs:
            rel = relpath_dot(a, os.path.dirname(b))
            files[a].err(lks[0].line, f"missing backlink: {files[b].rel} needs `Referred by: [...]({rel})` "
                                      "(run fix-backlinks)")
    for (b, a), lks in refs.items():
        if (a, b) not in deps:
            files[b].err(lks[0].line, f"{files[a].rel} is listed as referring here but has no "
                                      f"`Depends on:` link to {files[b].rel}")


def unknown_problems(u, lenient):
    """(severity, message) pairs for one unknown, judged on its own text."""
    missing = "warning" if lenient else "error"
    out = []
    if u.bad_name is not None:
        out.append(("error", f"unknown name [{u.bad_name}] must be lower-case letters, digits and hyphens"))
    if UNKNOWN_RE.search(re.sub(r"`[^`]*`", "", u.text)):      # a marker quoted in backticks is prose
        out.append(("warning", "more than one *UNKNOWN* on this line; write one unknown per line"))
    if u.follows:
        if "consequence" not in u.clauses:
            out.append(("warning", "*UNKNOWN* that follows another should state `Consequence:`"))
        extra = [f"`{c.capitalize()}:`" for c in ("kind", "proposed", "unlocks") if c in u.clauses]
        if extra:
            out.append(("warning", "*UNKNOWN* that follows another takes only `Consequence:`; "
                                   f"move {', '.join(extra)} to the declaration"))
        return out
    if not u.kind:
        out.append((missing, "*UNKNOWN* is missing `Kind:` (blocking or local)"))
    elif u.kind not in KINDS:
        out.append((missing, f"*UNKNOWN* has `Kind: {u.kind}`; it must be blocking or local"))
    elif u.kind == "local" and "proposed" not in u.clauses:
        out.append((missing, "*UNKNOWN* with `Kind: local` needs `Proposed:`"))
    if "consequence" not in u.clauses or "unlocks" not in u.clauses:
        out.append(("warning", "*UNKNOWN* should state `Consequence:` and `Unlocks:`"))
    return out


def name_problems(pairs):
    """(file, line, severity, message) for names declared twice and followers that match nothing."""
    out, first = [], {}
    for rel, u in pairs:
        if not u.name:
            continue
        if u.name in first:
            frel, fu = first[u.name]
            out.append((rel, u.line, "error", f"unknown name [{u.name}] is already declared at {frel}:{fu.line}"))
        else:
            first[u.name] = (rel, u)
    for rel, u in pairs:
        if u.follows and u.bad_name is None and u.follows not in first:
            out.append((rel, u.line, "error", f"`Follows [{u.follows}]` matches no declared unknown"))
    return out


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
    lines = read_text(path, "utf-8-sig").split("\n")
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


def slug_of(title):
    """The file-friendly form of a title: accents folded to ASCII, lower case, words joined by hyphens."""
    folded = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", folded.lower()).strip("-")


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
    title = pm.front.get("title", (0, ""))[1]
    if title and slug and wrist_profile.SLUG_RE.match(slug):
        expected = slug_of(title)
        if expected and slug != expected:
            out.append(("warning", line, f"slug '{slug}' is not the file-friendly form of the title "
                                         f"'{title}' (expected '{expected}')"))
    if not override and "profile" not in pm.front:
        out.append(("error", 1, f"{PREMISE_FILE} front matter needs `profile:`"))
    for key, message in profile.option_problems:
        out.append(("error", pm.front.get(key, (1, ""))[0], message))
    for q in profile.questions:
        if q.id in profile.premise_keys and pm.front.get(q.id, (0, ""))[1]:
            continue                # answered in the front matter, where the file set is decided
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
    if not os.path.isdir(args.wrist_dir):
        sys.exit(f"not a directory: {args.wrist_dir}")
    pm = read_premise(os.path.abspath(args.wrist_dir))
    name = args.profile or pm.front.get("profile", (0, ""))[1]
    if not name:
        for sev, ln, msg in pm.diags:
            sys.exit(f"{os.path.join(args.wrist_dir, PREMISE_FILE)}:{ln}: {msg}")
        sys.exit(f"no profile: give --profile or set `profile:` in {os.path.join(args.wrist_dir, PREMISE_FILE)}")
    try:
        profile = wrist_profile.load_profile(name)
    except wrist_profile.ProfileError as exc:
        sys.exit(f"profile error: {exc}")
    configure(profile)
    profile.set_premise({key: value for key, (_, value) in pm.front.items()})
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
    names = ", ".join(p for p, _ in expected[:12]) + (", ..." if len(expected) > 12 else "")
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
            sf.warn(1, f"no `Depends on:` link to {previous}'s stand-in with the relation `continues`")
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


def heading_path(sec):
    parts, s = [], sec
    while s is not None and s.level > 0:
        parts.append(s.title)
        s = s.parent
    return " > ".join(reversed(parts)) or "(top)"


def tree_unknowns(files, premise_unknowns):
    """Every unknown as (file, Unknown): stand-ins path order, then PREMISE.md."""
    pairs = [(sf.rel, u) for sf in sorted(files.values(), key=lambda f: f.rel) for u in sf.unknowns]
    pairs.extend((PREMISE_FILE, u) for u in premise_unknowns)
    return pairs


def decisions(pairs):
    """Declarations, each with the followers that name it, and followers that name nothing."""
    declared = [(rel, u, []) for rel, u in pairs if not u.follows]
    by_name = {}
    for _, u, followers in declared:
        if u.name:
            by_name.setdefault(u.name, followers)
    orphans = []
    for rel, u in pairs:
        if u.follows:
            by_name.get(u.follows, orphans).append((rel, u))
    return declared, orphans


def unknown_item(rel, u, followers=()):
    return {"file": rel, "line": u.line, "where": u.where, "text": u.text, "name": u.name, "follows": u.follows,
            "kind": u.kind, "proposed": u.clauses.get("proposed"), "consequence": u.clauses.get("consequence"),
            "unlocks": u.clauses.get("unlocks"),
            "followers": [{"file": r, "line": f.line, "where": f.where,
                           "consequence": f.clauses.get("consequence")} for r, f in followers]}


@command("unknowns", lambda p: p.add_argument("--json", action="store_true"))
def cmd_unknowns(args):
    wrist_root, files, profile, pm, slug = load_all(args)
    declared, orphans = decisions(tree_unknowns(files, pm.unknowns))
    if args.json:
        items = [unknown_item(rel, u, followers) for rel, u, followers in declared]
        items += [unknown_item(rel, u) for rel, u in orphans]
        print(json.dumps(items, indent=2))
        return 0
    if not declared and not orphans:
        print("No unknowns.")
        return 0
    groups = [("Blocking", [d for d in declared if d[1].kind == "blocking"]),
              ("Local", [d for d in declared if d[1].kind == "local"]),
              ("No valid kind", [d for d in declared if d[1].kind not in KINDS])]
    for title, group in groups:
        if not group:
            continue
        print(f"{title} ({len(group)}):")
        for rel, u, followers in group:
            label = f"[{u.name}] " if u.name else ""
            print(f"- {label}{rel}:{u.line} ({u.label}): {UNKNOWN_NAME_RE.sub('', u.text)}")
            for frel, f in followers:
                print(f"    followed at {frel}:{f.line} ({f.label}): "
                      f"{f.clauses.get('consequence', f.text)}")
        print()
    if orphans:
        print(f"Following an undeclared name ({len(orphans)}):")
        for rel, u in orphans:
            print(f"- {rel}:{u.line} ({u.label}): {u.text}")
        print()
    print(f"{len(declared)} unknowns")
    return 0


def stand_in_hash(sf):
    """Eight hex digits over the stand-in's words. Backlinks are left out, and so is how the text
    is wrapped, indented or spaced, so only a change to what it says moves the hash."""
    kept, in_backlinks, fence = [], False, None
    for line in sf.lines:
        fm = FENCE_RE.match(line)
        if fence:                                   # fenced text is content, whatever it looks like
            if fm and fm.group(1)[0] == fence[0] and len(fm.group(1)) >= len(fence) and not fm.group(2).strip():
                fence = None
            kept.append(line)
            continue
        if fm:
            fence, in_backlinks = fm.group(1), False
            kept.append(line)
            continue
        fld = FIELD_RE.match(line)
        if fld:
            backlink = CANON[fld.group(1).lower()] == "Referred by"
            in_backlinks = backlink and fld.group(2).strip() == ""   # block form: its bulleted links follow
            if backlink:
                continue
        elif in_backlinks and BULLET_LINK_RE.match(line):
            continue
        elif line.strip():
            in_backlinks = False
        kept.append(line)
    return hashlib.sha256(" ".join(" ".join(kept).split()).encode("utf-8")).hexdigest()[:8]




@command("fix-backlinks", lambda p: p.add_argument("--write", action="store_true"))
def cmd_fix_backlinks(args):
    wrist_root, files, profile, pm, slug = load_all(args)
    deps, refs = build_edges(wrist_root, files, report=False)
    inserts = defaultdict(list)  # target path -> [(line_index, text)]
    for (a, b), lks in sorted(deps.items()):
        if (b, a) in refs:
            continue
        tf = files[b]
        frags = {lk.target.partition("#")[2] for lk in lks} - {""}
        target_secs = [s for s in tf.sections if slugify(s.title) in frags] or \
                      [s for s in tf.sections if s.level == 1][:1]
        sym_secs = {lk.section.typed_owner() or lk.section for lk in lks}
        rel = relpath_dot(a, os.path.dirname(b))
        entries = set()
        for s in sym_secs:
            if s.level == 0:
                entries.add((files[a].impl_rel, ""))
            else:
                entries.add((s.qualified(), "#" + slugify(s.title) if s.level > 1 else ""))
        for ts in target_secs:
            idx = section_end(tf, ts)
            for nm, frag in sorted(entries):
                inserts[b].append((idx, f"- **Referred by:** [{nm}]({rel}{frag})"))
    if not inserts:
        print("All backlinks present.")
        return 0
    for path, items in sorted(inserts.items()):
        sf = files[path]
        print(f"{sf.rel}:")
        for idx, text in items:
            print(f"  + L{idx + 1}: {text}")
        if args.write:
            lines = list(sf.lines)
            for idx, text in reversed(sorted(items, key=lambda x: x[0])):
                lines.insert(idx, text)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("\n".join(lines))
    if not args.write:
        print("\n(dry run; pass --write to apply)")
    return 0


def section_end(sf, sec):
    """Line index (0-based) just after the section's own body, before the next heading."""
    later = [s.line for s in sf.sections if s.line > sec.line]
    end = (min(later) - 1) if later else len(sf.lines)
    # place directly after last field line within the section body, else before trailing blanks
    last_field = None
    for i in range(sec.line, end):
        if FIELD_RE.match(sf.lines[i]) or (BULLET_LINK_RE.match(sf.lines[i]) and last_field is not None
                                           and i == last_field + 1):
            last_field = i
    if last_field is not None:
        return last_field + 1
    while end > sec.line and not sf.lines[end - 1].strip():
        end -= 1
    return end


def field_text(sf, sec, label):
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
    order = [{"step": i, "stand_in": sf.rel, "realizes": sf.impl_rel,
              "function": profile.function_for(sf.impl_rel, slug),
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
        owed = missing_when_realized(sf, profile, slug)
        if owed:
            print(f"{shown}: its stand-in has no `{owed[0]}:` text; fill it in first")
            failed += 1
            continue
        entry = {"stand_in": stand_in_hash(sf), "realized": file_hash(impl),
                 "date": datetime.date.today().isoformat()}
        old = stamps.get(sf.impl_rel)
        old = old if isinstance(old, dict) else {}
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
    for sf in sorted_files(files, profile, slug):
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


@command("lint", lambda p: p.add_argument("--root"))
def cmd_lint(args):
    wrist_root, files, profile, pm, slug = load_all(args)
    root = project_root(args)
    try:
        items = profile.lint_items()
    except wrist_profile.ProfileError as exc:
        sys.exit(f"profile error: {exc}")
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
            "font": pm.front.get("font", (0, ""))[1], "title_page": profile.title_page}
    try:
        wrist_publish.run_commands(wrist_publish.plan_commands(sources, meta, "output", slug, PUBLISH_DIR), root)
    except wrist_publish.PublishError as exc:
        print(f"publish failed: {exc}")
        return 1
    print(f"published output/{slug}.epub and output/{slug}.pdf")
    return 0


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
