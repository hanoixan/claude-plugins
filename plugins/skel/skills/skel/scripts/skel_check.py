#!/usr/bin/env python3
"""skel_check.py: validate and analyze a Skel specification tree.

Subcommands
  check SKEL_DIR [--lenient]          validate grammar, traits and bidirectional links (and SYSTEM.md links)
  unknowns SKEL_DIR [--json]          list open decisions by kind, each once, with its followers
  order SKEL_DIR [--json]             implementation order (dependencies first; cycles grouped)
  batches SKEL_DIR [--json]           buildable batches of units; manifests are set aside
  status SKEL_DIR --root PROJECT      which stand-ins are implemented, pending, abstract, or missing
  fix-backlinks SKEL_DIR [--write]    insert missing `Referred by:` lines (dry-run by default)
  infer-roles SKEL_DIR [--write]      propose role: and unit: front matter (dry-run by default)

Standard library only. Exit code 1 if `check` finds errors.
"""
import argparse
import json
import os
import re
import sys
from collections import defaultdict

SKEL_SUFFIX = ".skel.md"

CODE_EXT = set("""py pyi js mjs cjs jsx ts tsx go rs java kt kts scala cs fs vb cpp cc cxx c h hpp hh hxx
m mm swift rb php lua dart ex exs erl hrl hs ml mli clj cljs groovy sh bash zsh fish ps1 r jl
vue svelte zig nim cr pl pm code""".split())
DATA_EXT = set("""json jsonc jsonl ndjson yaml yml toml csv tsv xml parquet avro proto ini env
graphql gql data""".split())
IAC_EXT = set("tf tfvars hcl bicep sql nomad iac".split())
EXTLESS = {"Dockerfile": "iac", "Containerfile": "iac", "Makefile": "code", "Procfile": "iac",
           "Jenkinsfile": "code", "Vagrantfile": "iac", "Gemfile": "data", "Brewfile": "data",
           "Justfile": "code", "Rakefile": "code"}
PLACEHOLDER_EXT = {"code", "data", "iac"}
LEVEL1 = {"code": "module", "data": "data", "iac": "infrastructure", "resource": "resource"}

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
TYPED_RE = re.compile(r"^(module|class|function|symbol|data|infrastructure|resource)\s*:\s*(.+)$", re.I)
FENCE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})(.*)$")
LINK_RE = re.compile(r"\[([^\]]+)\]\(\s*([^)\s]+)(?:\s+\"[^\"]*\")?\s*\)")
LABELS = ["Depends on", "Referred by", "Inputs", "Returns", "State changes", "Owns", "Access",
          "Required", "Failure modes", "Unknowns", "Source", "Data requirements"]
FIELD_RE = re.compile(
    r"^\s*(?:[-*+]\s+)?(?:\*\*|__)?(" + "|".join(re.escape(l) for l in LABELS) +
    r")(?:\*\*|__)?\s*:(?:\*\*|__)?\s*(.*)$", re.I)
CANON = {l.lower(): l for l in LABELS}
UNKNOWN_RE = re.compile(r"\*{1,2}UNKNOWN\*{1,2}\s*:\s*(.*)")
INFORMAL_RE = re.compile(r"(\bTBD\b|\bTODO\b|\bFIXME\b|\?\?\?|(?<![*\w])UNKNOWN(?![*\w]))")
NONE_RE = re.compile(r"^\s*(none|n/?a)\b", re.I)
BULLET_LINK_RE = re.compile(r"^\s*[-*+]\s+.*\[[^\]]+\]\([^)]+\)")
EXTERNAL_RE = re.compile(r"^[a-z][a-z0-9+.-]*:", re.I)
DOTTED_RE = re.compile(r"^`?([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+)`?$")
SYSTEM_FILE = "SYSTEM.md"
UNKNOWN_NAME_RE = re.compile(r"^\[([a-z0-9][a-z0-9-]*)\](?!\()\s*")
BRACKET_RE = re.compile(r"^\[([^\]]*)\](?!\()\s*")      # a leading [..] that is not a markdown link
FOLLOWS_RE = re.compile(r"^(?i:follows)\s+\[([^\]]*)\]\s*\.?\s*")
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
# A clause label opens the text or follows the end of a sentence, so "kind:" inside prose is not one.
CLAUSE_RE = re.compile(r"(?:^|(?<=[.!?;)`*]\s))\**(Kind|Proposed|Consequence|Unlocks)\**:\**\s*")
KINDS = ("blocking", "local")
ROLES = ("product", "test", "manifest")
META_RE = re.compile(r"^\s*([A-Za-z_]+)\s*:\s*(.*)$")
MANIFEST_NAMES = {"CMakeLists.txt", "CMakePresets.json", "CMakeUserPresets.json", "Makefile", "makefile",
                  "GNUmakefile", "Justfile", "Rakefile", "Gemfile", "package.json", "tsconfig.json",
                  "pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "Cargo.toml", "go.mod",
                  "build.gradle", "build.gradle.kts", "settings.gradle", "pom.xml", "meson.build",
                  "BUILD", "BUILD.bazel", "WORKSPACE"}
TEST_DIRS = {"test", "tests", "spec", "specs", "__tests__"}
TEST_NAME_RE = re.compile(r"^(test_.+|.+_test\.[^.]+|.+\.(test|spec)\.[^.]+|.+Test\.[^.]+|conftest\.py)$")
UNSURE_DIRS = {"tools", "scripts", "examples"}
SOURCE_EXT = {"c", "cc", "cpp", "cxx", "m", "mm"}
HEADER_EXT = {"h", "hh", "hpp", "hxx"}

LEVEL_FIELDS = {
    "module": ["Owns", "Access"],
    "class": ["Inputs", "State changes", "Owns", "Access"],
    "function": ["Inputs", "Returns", "State changes", "Access"],
    "symbol": ["Access"],
}


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
    def __init__(self, label, text, target, line, section):
        self.label, self.text, self.target, self.line, self.section = label, text, target, line, section


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
        self.what = parts[0].strip()
        self.clauses = {}
        for label, value in zip(parts[1::2], parts[2::2]):
            self.clauses.setdefault(label.lower(), value.strip())

    @property
    def kind(self):
        return self.clauses.get("kind", "").strip(" .`*_").lower()

    @property
    def where(self):
        return heading_path(self.section) if self.section is not None else "(system)"

    @property
    def label(self):
        """`where` as printed inside brackets in text output."""
        return heading_path(self.section) if self.section is not None else "system"


class SkelFile:
    def __init__(self, path, skel_root):
        self.path = os.path.abspath(path)
        self.rel = os.path.relpath(self.path, skel_root)
        self.impl_rel = self.rel[: -len(SKEL_SUFFIX)]
        base = os.path.basename(self.impl_rel)
        self.ext = base.rsplit(".", 1)[1] if "." in base else ""
        self.base = base
        self.kind = None
        self.kind_override = None
        self.meta = {}          # front matter: key -> (line, value)
        self.root = Section(0, None, "", "", 0)
        self.sections = []
        self.unknowns = []      # [Unknown]
        self.lines = []
        self.diags = []         # (severity, line, msg)

    @property
    def abstract(self):
        return self.ext in PLACEHOLDER_EXT

    @property
    def role(self):
        return self.meta["role"][1].lower() if "role" in self.meta else None

    def err(self, line, msg):
        self.diags.append(("error", line, msg))

    def warn(self, line, msg):
        self.diags.append(("warning", line, msg))

    def all_links(self):
        out = list(self.root.links)
        for s in self.sections:
            out.extend(s.links)
        return out


def infer_kind(sf):
    if sf.kind_override:
        return sf.kind_override
    if not sf.ext:
        return EXTLESS.get(sf.base, "resource")
    e = sf.ext.lower()
    if e in CODE_EXT:
        return "code"
    if e in DATA_EXT:
        return "data"
    if e in IAC_EXT:
        return "iac"
    return "resource"


def parse(path, skel_root):
    sf = SkelFile(path, skel_root)
    with open(path, encoding="utf-8") as fh:
        sf.lines = fh.read().split("\n")
    lines = sf.lines
    start = 0
    if lines and lines[0].strip() == "---":
        for j in range(1, len(lines)):
            if lines[j].strip() == "---":
                for i, l in enumerate(lines[1:j], 2):
                    m = META_RE.match(l)
                    if m:
                        sf.meta[m.group(1).lower()] = (i, m.group(2).strip())
                start = j + 1
                break
    if "kind" in sf.meta:
        ln, value = sf.meta["kind"]
        k = value.split()[0].lower() if value else ""
        if k in LEVEL1:
            sf.kind_override = k
        else:
            sf.err(ln, f"front matter kind '{k}' must be one of {sorted(LEVEL1)}")
    sf.kind = infer_kind(sf)

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
                found = LINK_RE.findall(value)
                for text, target in found:
                    cur.links.append(Link(label, text, target, ln, cur))
                if not found:
                    if value.strip() == "":
                        pending = (label, ln)
                    elif not NONE_RE.match(value) and not UNKNOWN_RE.search(value):
                        sf.err(ln, f"`{label}:` has no markdown link; use [symbol](path) or 'none'")
        elif pending and BULLET_LINK_RE.match(line):
            for text, target in LINK_RE.findall(line):
                cur.links.append(Link(pending[0], text, target, ln, cur))
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


def validate_file(sf, lenient):
    miss = sf.warn if lenient else sf.err
    # front matter
    if sf.role is None:
        miss(1, "missing `role:` in front matter (product, test or manifest); `infer-roles` can propose one")
    elif sf.role not in ROLES:
        sf.err(sf.meta["role"][0], f"front matter role '{sf.role}' must be one of {list(ROLES)}")
    if "untested" in sf.meta:
        ln, reason = sf.meta["untested"]
        if sf.role != "product":
            sf.err(ln, "`untested:` is only for `role: product` stand-ins")
        elif not reason:
            sf.err(ln, "`untested:` needs a reason")
    # naming
    if not sf.ext and sf.base not in EXTLESS:
        sf.err(1, f"stand-in name must be <file>.<ext>{SKEL_SUFFIX} (got '{sf.base}{SKEL_SUFFIX}')")
    # level-1 heading
    l1 = [s for s in sf.sections if s.level == 1]
    expected = LEVEL1[sf.kind]
    if len(l1) != 1:
        sf.err(l1[1].line if len(l1) > 1 else 1,
               f"expected exactly one level-1 heading `# {expected}: <name>` (found {len(l1)})")
    elif l1[0].kind != expected:
        sf.err(l1[0].line, f"{sf.kind} file must start with `# {expected}: <name>`")
    if sf.root.fields:
        ln = min(v[0][0] for v in sf.root.fields.values())
        sf.warn(ln, "fields before the first heading are not attached to any symbol")

    for s in sf.sections:
        if s.kind is None:
            continue
        if s.level == 1:
            continue
        par = s.parent.typed_owner() if s.parent else None
        pk = par.kind if par else None
        if sf.kind == "code":
            ok = ((s.kind == "class" and s.level == 2 and pk == "module") or
                  (s.kind == "function" and ((s.level == 2 and pk == "module") or (s.level == 3 and pk == "class"))) or
                  (s.kind == "symbol" and ((s.level == 2 and pk == "module") or (s.level == 3 and pk == "class"))))
            if not ok:
                sf.err(s.line, f"`{'#' * s.level} {s.kind}:` not allowed here; hierarchy is "
                               "# module > ## class|function|symbol > ### function|symbol (under class)")
        elif sf.kind == "iac":
            if not (s.kind == "resource" and s.level == 2 and pk == "infrastructure"):
                sf.err(s.line, "iac files allow only `## resource: <name>` under `# infrastructure:`")
        else:
            sf.err(s.line, f"typed heading `{s.kind}:` not allowed in a {sf.kind} file")

    # per-level code fields
    if sf.kind == "code":
        for s in sf.sections:
            if s.kind in LEVEL_FIELDS:
                f = own_fields(s)
                for label in LEVEL_FIELDS[s.kind]:
                    if label not in f:
                        miss(s.line, f"{s.kind} '{s.name}' is missing `{label}:`")

    # data specifics
    ff = file_fields(sf)
    if sf.kind == "data":
        if "Source" not in ff:
            sf.err(1, "data file is missing `Source:` (hand-authored | generated | external)")
        schema = find_untyped(sf, "Schema")
        if not schema:
            sf.err(1, "data file is missing a `## Schema` section")
        elif sum(own_count(s, "fences") for s in schema) == 0:
            sf.err(schema[0].line, "`## Schema` must contain a fenced block")
        if any("generat" in v.lower() for _, v in ff.get("Source", [])):
            gen = find_untyped(sf, "Generation")
            if not gen:
                sf.err(ff["Source"][0][0], "generated data needs a `## Generation` section")
            else:
                if sum(own_count(s, "any_links") for s in gen) == 0:
                    sf.err(gen[0].line, "`## Generation` must link to the generating tool(s)")
                if sum(own_count(s, "fences") for s in gen) == 0:
                    sf.err(gen[0].line, "`## Generation` must include a fenced development-usage example")

    # iac specifics
    if sf.kind == "iac":
        res = [s for s in sf.sections if s.kind == "resource"]
        if not res:
            sf.err(1, "iac file must declare at least one `## resource: <name>`")
        for r in res:
            f = own_fields(r)
            if "Data requirements" not in f:
                miss(r.line, f"resource '{r.name}' is missing `Data requirements:`")
            if "Referred by" not in f:
                sf.err(r.line, f"resource '{r.name}' must list consumers with `Referred by:`")
            elif all(NONE_RE.match(v) for _, v in f["Referred by"]):
                sf.warn(r.line, f"resource '{r.name}' has no known consumers")

    # five basic questions
    for label, q in [("Required", "Is this always required?"), ("Failure modes", "Known failure modes"),
                     ("Depends on", "What does this depend on?"), ("Referred by", "What depends on this?")]:
        if label not in ff:
            sf.err(1, f"missing `{label}:` (answers '{q}'); use 'none' if that is the answer")
    if not sf.unknowns and "Unknowns" not in ff:
        sf.err(1, "no *UNKNOWN* entries and no `Unknowns: none`")


def load_tree(skel_dir):
    skel_root = os.path.abspath(skel_dir)
    if not os.path.isdir(skel_root):
        sys.exit(f"not a directory: {skel_dir}")
    files = {}
    for dp, dns, fns in os.walk(skel_root):
        dns[:] = sorted(d for d in dns if not d.startswith("."))
        for fn in sorted(fns):
            if fn.endswith(SKEL_SUFFIX):
                sf = parse(os.path.join(dp, fn), skel_root)
                files[sf.path] = sf
    return skel_root, files


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
    symbols = [s for s in secs if s.level > 1 and s.kind in ("class", "function", "symbol")]
    if dotted and symbols:
        module = next((s.name for s in target.sections if s.level == 1), "")
        names = {s.qualified() for s in symbols}
        if dotted.group(1) not in names | {f"{module}.{n}" for n in names}:
            return [("warning", f"link text '{dotted.group(1)}' does not match the heading it points at "
                                f"({', '.join(sorted(names))})")]
    return []


def build_edges(skel_root, files, report=True):
    deps = defaultdict(list)   # (A,B) -> [Link]   A depends on B
    refs = defaultdict(list)   # (B,A) -> [Link]   B says it is referred by A
    for sf in files.values():
        for lk in sf.all_links():
            if EXTERNAL_RE.match(lk.target):
                if lk.label == "Referred by" and report:
                    sf.err(lk.line, "`Referred by:` must point at a .skel.md file, not a URL")
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
            inside = os.path.commonpath([tgt, skel_root]) == skel_root
            if tgt not in files:
                if report:
                    if lk.label == "Referred by":
                        sf.err(lk.line, "`Referred by:` must point at a .skel.md file")
                    elif inside:
                        sf.warn(lk.line, "dependency inside skel/ should target a .skel.md stand-in")
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


def read_system(skel_root):
    """Unknowns, links and heading slugs of SYSTEM.md, which is context rather than a stand-in."""
    unknowns, links, slugs = [], [], set()
    path = os.path.join(skel_root, SYSTEM_FILE)
    if not os.path.exists(path):
        return unknowns, links, slugs
    with open(path, encoding="utf-8") as fh:
        fence = False
        for ln, line in enumerate(fh, 1):
            if FENCE_RE.match(line):
                fence = not fence
                continue
            if fence:
                continue
            hm = HEADING_RE.match(line.rstrip("\n"))
            if hm:
                slugs.add(slugify(hm.group(2)))
                continue
            um = UNKNOWN_RE.search(line)
            if um:
                unknowns.append(Unknown(ln, um.group(1).strip()))
            links.extend((ln, text, target) for text, target in LINK_RE.findall(line))
    return unknowns, links, slugs


def check_system(skel_root, files, links, slugs):
    diags = []
    for ln, text, target in links:
        if EXTERNAL_RE.match(target):
            continue
        path, _, frag = target.partition("#")
        if path == "":
            if frag and frag not in slugs:
                diags.append(("error", ln, f"fragment '#{frag}' does not match any heading in this file"))
            continue
        tgt = os.path.normpath(os.path.join(skel_root, path))
        if not os.path.exists(tgt):
            diags.append(("error", ln, f"link target does not exist: {target}"))
        elif frag and tgt in files:
            diags.extend((sev, ln, msg) for sev, msg in fragment_problems(text, frag, files[tgt], path))
    return diags


def resolve_units(files, report=True):
    """Map each stand-in path to its unit's primary path; a bad `unit:` is reported and ignored."""
    primary = {}
    for sf in files.values():
        primary[sf.path] = sf.path
        if "unit" not in sf.meta:
            continue
        ln, value = sf.meta["unit"]
        tgt = os.path.normpath(os.path.join(os.path.dirname(sf.path), value))
        if tgt == sf.path:
            problem = "`unit:` names this stand-in itself"
        elif tgt not in files:
            problem = f"`unit:` target is not a stand-in in this tree: {value}"
        elif "unit" in files[tgt].meta:
            problem = f"`unit:` target {value} has a `unit:` of its own; name the primary stand-in"
        elif files[tgt].role != sf.role:
            problem = f"`unit:` target {value} has role '{files[tgt].role}', not '{sf.role}'"
        else:
            primary[sf.path] = tgt
            continue
        if report:
            sf.err(ln, problem)
    return primary


def unit_members(files, primary):
    """Primary path -> its member stand-ins, the primary first and the rest in path order."""
    members = defaultdict(list)
    for sf in sorted(files.values(), key=lambda f: (f.path != primary[f.path], f.rel)):
        members[primary[sf.path]].append(sf)
    return members


def untested_units(files, deps, primary):
    """Primaries of concrete product code units that no test stand-in depends on."""
    tested = {primary[b] for (a, b) in deps if files[a].role == "test"}
    out = []
    for head, group in unit_members(files, primary).items():
        if files[head].role != "product" or head in tested:
            continue
        if any("untested" in m.meta or m.abstract for m in group):
            continue
        if any(m.kind == "code" and any(s.kind in ("class", "function") for s in m.sections) for m in group):
            out.append(files[head])
    return out


def unknown_problems(u, lenient):
    """(severity, message) pairs for one unknown, judged on its own text."""
    missing = "warning" if lenient else "error"
    out = []
    if u.bad_name is not None:
        out.append(("error", f"unknown name [{u.bad_name}] must be lower-case letters, digits and hyphens"))
    if u.follows:
        if "consequence" not in u.clauses:
            out.append(("warning", "*UNKNOWN* that follows another should state `Consequence:`"))
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


def cmd_check(args):
    skel_root, files = load_tree(args.skel_dir)
    for sf in files.values():
        validate_file(sf, args.lenient)
    deps, refs = build_edges(skel_root, files)
    check_bidirectional(files, deps, refs)
    primary = resolve_units(files)
    for sf in untested_units(files, deps, primary):
        sf.warn(1, "no test stand-in depends on this unit; link one or state `untested: <reason>` in front matter")
    sys_unknowns, sys_links, sys_slugs = read_system(skel_root)
    diags = {sf.rel: sf.diags for sf in files.values()}
    diags[SYSTEM_FILE] = check_system(skel_root, files, sys_links, sys_slugs)
    pairs = tree_unknowns(files, sys_unknowns)
    for rel, u in pairs:
        diags[rel].extend((sev, u.line, msg) for sev, msg in unknown_problems(u, args.lenient))
    for rel, line, sev, msg in name_problems(pairs):
        diags[rel].append((sev, line, msg))
    ne = nw = 0
    for rel in sorted(r for r in diags if r != SYSTEM_FILE) + [SYSTEM_FILE]:
        for sev, ln, msg in sorted(diags[rel], key=lambda d: d[1]):
            print(f"{os.path.join(args.skel_dir, rel)}:{ln}: {sev}: {msg}")
            ne += sev == "error"
            nw += sev == "warning"
    n_unk = len(decisions(pairs)[0])
    n_abs = sum(f.abstract for f in files.values())
    print(f"\n{len(files)} stand-ins, {len(deps)} dependency edges, {n_unk} unknowns, "
          f"{n_abs} abstract (placeholder extension); {ne} errors, {nw} warnings")
    return 1 if ne else 0


def heading_path(sec):
    parts, s = [], sec
    while s is not None and s.level > 0:
        parts.append(s.title)
        s = s.parent
    return " > ".join(reversed(parts)) or "(top)"


def tree_unknowns(files, system_unknowns):
    """Every unknown as (file, Unknown): stand-ins in path order, then SYSTEM.md."""
    pairs = [(sf.rel, u) for sf in sorted(files.values(), key=lambda f: f.rel) for u in sf.unknowns]
    pairs.extend((SYSTEM_FILE, u) for u in system_unknowns)
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


def unknown_item(rel, u):
    return {"file": rel, "line": u.line, "where": u.where, "text": u.text}


def cmd_unknowns(args):
    skel_root, files = load_tree(args.skel_dir)
    declared, orphans = decisions(tree_unknowns(files, read_system(skel_root)[0]))
    if args.json:
        items = []
        for rel, u, followers in declared:
            item = unknown_item(rel, u)
            item.update(name=u.name, kind=u.kind, proposed=u.clauses.get("proposed"),
                        consequence=u.clauses.get("consequence"), unlocks=u.clauses.get("unlocks"),
                        followers=[{"file": r, "line": f.line, "where": f.where,
                                    "consequence": f.clauses.get("consequence")} for r, f in followers])
            items.append(item)
        for rel, u in orphans:
            items.append(dict(unknown_item(rel, u), follows=u.follows))
        print(json.dumps(items, indent=2))
        return 0
    if not declared and not orphans:
        print("No unknowns.")
        return 0
    groups = [("Blocking", [d for d in declared if d[1].kind == "blocking"]),
              ("Local", [d for d in declared if d[1].kind == "local"]),
              ("No kind stated", [d for d in declared if d[1].kind not in KINDS])]
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


def sccs(nodes, edges):
    index, low, on, stack, out, counter = {}, {}, set(), [], [], [0]
    sys.setrecursionlimit(max(10000, len(nodes) * 4))

    def visit(v):
        index[v] = low[v] = counter[0]
        counter[0] += 1
        stack.append(v)
        on.add(v)
        for w in edges.get(v, ()):
            if w not in index:
                visit(w)
                low[v] = min(low[v], low[w])
            elif w in on:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            comp = []
            while True:
                w = stack.pop()
                on.discard(w)
                comp.append(w)
                if w == v:
                    break
            out.append(sorted(comp))
    for v in sorted(nodes):
        if v not in index:
            visit(v)
    return out  # Tarjan emits components in reverse topological order of the edge direction


def cmd_order(args):
    skel_root, files = load_tree(args.skel_dir)
    deps, _ = build_edges(skel_root, files, report=False)
    edges = defaultdict(set)
    for a, b in deps:
        edges[a].add(b)
    comps = sccs(list(files), edges)  # dependencies come out first because edges point at dependencies
    steps = []
    for i, comp in enumerate(comps, 1):
        steps.append({"step": i, "cycle": len(comp) > 1, "files": [{
            "skel": files[p].rel, "implements": files[p].impl_rel, "kind": files[p].kind,
            "abstract": files[p].abstract, "unknowns": len(files[p].unknowns),
            "depends_on": sorted(files[b].rel for b in edges.get(p, ()))} for p in comp]})
    if args.json:
        print(json.dumps(steps, indent=2))
        return 0
    for st in steps:
        tag = "  (cycle: implement together, consider breaking it)" if st["cycle"] else ""
        print(f"{st['step']}.{tag}")
        for f in st["files"]:
            flags = []
            if f["abstract"]:
                flags.append("ABSTRACT")
            if f["unknowns"]:
                flags.append(f"{f['unknowns']} UNKNOWN")
            fl = f"  [{', '.join(flags)}]" if flags else ""
            print(f"   {f['implements']}  ({f['kind']}){fl}")
    return 0


def cmd_batches(args):
    skel_root, files = load_tree(args.skel_dir)
    deps, _ = build_edges(skel_root, files, report=False)
    primary = resolve_units(files, report=False)
    members = unit_members(files, primary)
    manifests = sorted(m.impl_rel for p, group in members.items() if files[p].role == "manifest" for m in group)
    nodes = sorted(p for p in members if files[p].role != "manifest")
    edges = defaultdict(set)
    for (a, b) in deps:
        ua, ub = primary[a], primary[b]
        if ua != ub and files[ua].role != "manifest" and files[ub].role != "manifest":
            edges[ua].add(ub)
    comps = sccs(nodes, edges)  # dependencies come out first, so every level below is already known
    comp_of = {p: i for i, comp in enumerate(comps) for p in comp}
    level = {}
    for i, comp in enumerate(comps):
        below = {comp_of[d] for p in comp for d in edges.get(p, ()) if comp_of[d] != i}
        level[i] = 1 + max((level[j] for j in below), default=0)
    batches = defaultdict(list)
    for i, comp in enumerate(comps):
        for p in comp:
            group = members[p]
            batches[level[i]].append({
                "unit": files[p].impl_rel, "files": [m.impl_rel for m in group],
                "role": files[p].role or "product", "cycle": len(comp) > 1,
                "abstract": any(m.abstract for m in group), "unknowns": sum(len(m.unknowns) for m in group),
                "depends_on": sorted(files[d].impl_rel for d in edges.get(p, ()))})
    result = {"manifests": manifests,
              "batches": [{"batch": n, "units": sorted(batches[n], key=lambda u: u["unit"])} for n in sorted(batches)]}
    if args.json:
        print(json.dumps(result, indent=2))
        return 0
    if manifests:
        print("Manifests (create with batch 1, extend with every batch):")
        for path in manifests:
            print(f"  {path}")
        print()
    for batch in result["batches"]:
        print(f"Batch {batch['batch']}:")
        for u in batch["units"]:
            extra = f"  (+ {', '.join(u['files'][1:])})" if len(u["files"]) > 1 else ""
            flags = [f"[{u['role']}]"] if u["role"] == "test" else []
            if u["cycle"]:
                flags.append("[cycle]")
            if u["abstract"]:
                flags.append("[ABSTRACT]")
            if u["unknowns"]:
                flags.append(f"[{u['unknowns']} UNKNOWN]")
            print(f"  {u['unit']}{extra}{'  ' + ' '.join(flags) if flags else ''}")
        print()
    return 0


IGNORE_DIRS = {".git", "node_modules", "venv", ".venv", "dist", "build", "target", "__pycache__",
               ".idea", ".vscode", "skel", ".next", "out", "vendor"}


def cmd_status(args):
    skel_root, files = load_tree(args.skel_dir)
    root = os.path.abspath(args.root)
    implemented, pending, abstract = [], [], []
    specified = set()
    for sf in sorted(files.values(), key=lambda f: f.rel):
        impl = os.path.join(root, sf.impl_rel)
        specified.add(os.path.normpath(impl))
        (implemented if os.path.exists(impl) else abstract if sf.abstract else pending).append(sf)
    unspecified = []
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in IGNORE_DIRS and not d.startswith(".")
                  and os.path.abspath(os.path.join(dp, d)) != skel_root]
        for fn in fns:
            ext = fn.rsplit(".", 1)[-1].lower() if "." in fn else ""
            if (ext in CODE_EXT | IAC_EXT and ext not in PLACEHOLDER_EXT) or fn in EXTLESS:
                p = os.path.normpath(os.path.join(dp, fn))
                if p not in specified:
                    unspecified.append(os.path.relpath(p, root))
    print(f"Implemented ({len(implemented)}):")
    for sf in implemented:
        print(f"  {sf.impl_rel}")
    for title, group in (("Pending", pending), ("Abstract, adapt before implementing", abstract)):
        print(f"{title} ({len(group)}):")
        for sf in group:
            unk = f"  [{len(sf.unknowns)} UNKNOWN]" if sf.unknowns else ""
            print(f"  {sf.impl_rel}{unk}")
    print(f"Code/IaC files with no stand-in ({len(unspecified)}):")
    for p in sorted(unspecified):
        print(f"  {p}")
    return 0


def infer_role(sf):
    """(role, reason it is unsure or None), judged from the implemented file's path alone."""
    parts = sf.impl_rel.split(os.sep)
    name, dirs = parts[-1], parts[:-1]
    if name in MANIFEST_NAMES or name.endswith(".cmake"):
        return "manifest", None
    if TEST_NAME_RE.match(name) or any(d in TEST_DIRS for d in dirs):
        return "test", None
    for d in dirs:
        if d in UNSURE_DIRS:
            return "product", f"under {d}/, so it may not be delivered"
    return "product", None


def infer_unit(sf, files):
    """(header stand-in this source is built with or None, reason it is unsure or None)."""
    if sf.ext.lower() not in SOURCE_EXT:
        return None, None
    stem = sf.base.rsplit(".", 1)[0]
    fits = []
    for other in files.values():
        if os.path.dirname(other.path) != os.path.dirname(sf.path) or other.ext.lower() not in HEADER_EXT:
            continue
        ostem = other.base.rsplit(".", 1)[0]
        if stem == ostem or (stem.startswith(ostem) and stem[len(ostem)] in "_-."):
            fits.append((len(ostem), other))
    if not fits:
        return None, None
    longest = max(n for n, _ in fits)
    winners = sorted((o for n, o in fits if n == longest), key=lambda o: o.path)
    reason = None
    if len(winners) > 1:
        reason = "more than one header fits: " + ", ".join(os.path.basename(o.path) for o in winners)
    return winners[0], reason


def add_front_matter(sf, pairs):
    """Write `key: value` lines into the stand-in's front matter, creating the block if it has none."""
    lines = list(sf.lines)
    new = [f"{key}: {value}" for key, value in pairs]
    close = None
    if lines and lines[0].strip() == "---":
        close = next((j for j in range(1, len(lines)) if lines[j].strip() == "---"), None)
    if close is None:
        lines = ["---", *new, "---"] + lines
    else:
        lines[close:close] = new
    with open(sf.path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


def cmd_infer_roles(args):
    skel_root, files = load_tree(args.skel_dir)
    deps, _ = build_edges(skel_root, files, report=False)
    roles, unsure = {}, {}
    for sf in files.values():
        roles[sf.path], unsure[sf.path] = (sf.role, None) if sf.role is not None else infer_role(sf)
    for (a, b) in sorted(deps):
        if files[b].role is None and roles[b] == "test" and roles[a] == "product" and not unsure[b]:
            unsure[b] = f"product stand-in {files[a].rel} depends on it"
    n_write = n_unsure = 0
    for sf in sorted(files.values(), key=lambda f: f.rel):
        sure, doubts = [], []
        if sf.role is None:
            if unsure[sf.path]:
                doubts.append(("role", roles[sf.path], unsure[sf.path]))
            else:
                sure.append(("role", roles[sf.path]))
        if "unit" not in sf.meta:
            header, reason = infer_unit(sf, files)
            if header is not None:
                rel = "./" + os.path.basename(header.path)
                if not reason and roles[header.path] != roles[sf.path]:
                    reason = f"the header's role is {roles[header.path]}, this one's is {roles[sf.path]}"
                if reason:
                    doubts.append(("unit", rel, reason))
                else:
                    sure.append(("unit", rel))
        if not sure and not doubts:
            continue
        print(f"{sf.rel}:")
        for key, value in sure:
            print(f"  + {key}: {value}")
        for key, value, reason in doubts:
            print(f"  ? {key}: {value}  (unsure: {reason})")
        n_write += len(sure)
        n_unsure += len(doubts)
        if args.write and sure:
            add_front_matter(sf, sure)
    if not n_write and not n_unsure:
        print("Nothing to infer.")
        return 0
    print(f"\n{n_write} to write, {n_unsure} unsure (never written; set those by hand)")
    if not args.write:
        print("(dry run; pass --write to apply)")
    return 0


def cmd_fix_backlinks(args):
    skel_root, files = load_tree(args.skel_dir)
    deps, refs = build_edges(skel_root, files, report=False)
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


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("check"); p.add_argument("skel_dir"); p.add_argument("--lenient", action="store_true",
                                                                            help="report missing fields as warnings; link and naming errors still fail")
    p = sub.add_parser("unknowns"); p.add_argument("skel_dir"); p.add_argument("--json", action="store_true")
    p = sub.add_parser("order"); p.add_argument("skel_dir"); p.add_argument("--json", action="store_true")
    p = sub.add_parser("status"); p.add_argument("skel_dir"); p.add_argument("--root", required=True)
    p = sub.add_parser("fix-backlinks"); p.add_argument("skel_dir"); p.add_argument("--write", action="store_true")
    p = sub.add_parser("infer-roles"); p.add_argument("skel_dir"); p.add_argument("--write", action="store_true")
    p = sub.add_parser("batches"); p.add_argument("skel_dir"); p.add_argument("--json", action="store_true")
    args = ap.parse_args()
    fn = {"check": cmd_check, "unknowns": cmd_unknowns, "order": cmd_order, "status": cmd_status,
          "fix-backlinks": cmd_fix_backlinks, "infer-roles": cmd_infer_roles, "batches": cmd_batches}[args.cmd]
    sys.exit(fn(args))


if __name__ == "__main__":
    main()
