#!/usr/bin/env python3
"""Ask questions as recorded rounds, rate the concerns behind them, and predict answers.

Files, all in the store (.question-refiner/ at the git root, or --dir):
  interviews.md   every question asked: its choices, their annotations, the prediction and the answer
  weights.md      the concerns, the tags they cover, and each person's ratings
  round.md        the round being asked (git-ignored); deleted when the round is recorded

Commands (--by defaults to `git config user.name`; --dir overrides the store):
  parse                                       validate the store
  concerns [--json]                           tags with no concern; concerns this person has not rated
  tag TAG C<n> | tag TAG --new NAME MEANING
  rate C<n>=V ... [--date YYYY-MM-DD]
  fit [--json]                                stated against fitted weights
  predict                                     mark the round's predicted choices
  record --answers "Q1=2, Q2=Other, Q3=none" [--asked STAMP]
  hits [--json]                               hit rates of logged predictions
  domains [add DOMAIN ... [--fresh]]          list the domains, or create or extend weights.md from the catalog
  import SKEL_FOLDER                          copy skel 3.1.0 interview files into the store
  exempt --question TEXT --reason TEXT        log a question with no trade-off; the gate passes it for 10 minutes

Standard library only.
"""
import argparse
import datetime
import json
import math
import os
import re
import secrets
import subprocess
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass, field

STORE = ".question-refiner"
LOG = "interviews.md"
WEIGHTS = "weights.md"
DRAFT = "round.md"
LOG_TITLE = "# question-refiner interviews"
WEIGHTS_TITLE = "# question-refiner weights"
DRAFT_TITLE = "# question-refiner round"
EXEMPT = "exempt.md"
EXEMPT_TITLE = "# question-refiner exempt questions"
EXEMPT_WINDOW = 600     # seconds an exempt question passes the gate
EXEMPT_RE = re.compile(r"^- (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} [+-]\d{4}) · by: (.+?) · question: (.+?) · "
                       r"reason: (.+)$")
LEGACY_LOG = ".interviews.md"
LEGACY_WEIGHTS = ".interview-weights.md"
LEGACY_DRAFT = ".interview-round.md"
MOVED = ".interview-moved.md"
LEGACY = {LEGACY_LOG: ("# skel interviews", LOG, LOG_TITLE),
          LEGACY_WEIGHTS: ("# skel interview weights", WEIGHTS, WEIGHTS_TITLE),
          LEGACY_DRAFT: ("# skel interview round", DRAFT, DRAFT_TITLE)}
CATALOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "references", "concerns.md")
DOMAINS = ("software", "infrastructure", "product", "fiction", "nonfiction", "research", "planning")

SEP = " · "
RECOMMENDED = "(Recommended)"
DECLINED = "none (declined)"
STAMP_FORMAT = "%Y-%m-%d %H:%M:%S %z"
T = 0.1             # softmax temperature
LAMBDA = 0.02       # pull of the fit toward the stated ratings
STEPS = 1000        # gradient-ascent steps
RATE = 0.5          # step size, divided by the number of fitted questions
MIN_TRACERS = 5     # tracers a person needs before their weights are fitted

TAG_RE = re.compile(r"^(?:NEW:)?[a-z0-9]+(?:-[a-z0-9]+)*$")
RECORD_RE = re.compile(r"^## Q(\d+)$")
CHOICE_RE = re.compile(r"^- (<sel> )?(\* )?\*\*(.+?)\*\*:(?: (.*))?$")
ANNOTATION_RE = re.compile(r"^    (concern|raises|addresses): (.*)$")
FIELD_RE = re.compile(r"^(answer|prediction|concern-only|axis|probes|round-id): (.*)$")
CONCERN_RE = re.compile(r"^## C(\d+) (\S.*)$")
RATING_RE = re.compile(r"^(\d+(?:\.\d+)?) · by: (.+) · (\d{4}-\d{2}-\d{2})$")
AXIS_RE = re.compile(r"^C(\d+) .+ vs C(\d+) .+$")
PAIR_RE = re.compile(r"^(\S+) ([123])$")
META_KEYS = ("header", "round", "select", "asked", "by")
FIELD_ORDER = ("answer", "prediction", "concern-only", "axis", "probes", "round-id")
MARK_ORDER = ("probe", "tracer")


class Problems:
    def __init__(self):
        self.errors, self.warnings = [], []

    def error(self, path, line, message):
        self.errors.append(f"{os.path.basename(path)}:{line}: {message}")

    def warn(self, path, line, message):
        self.warnings.append(f"{os.path.basename(path)}:{line}: {message}")


@dataclass
class Choice:
    body: str                 # "**label**: description", exactly as written
    label: str
    sel: bool
    predicted: bool
    line: int                 # index of the choice line in its file
    annotations: list = field(default_factory=list)   # (name, raw value), in file order
    concern: str = None
    raises: list = None       # [(tag, severity)]; None when the line is missing
    addresses: list = None

    @property
    def recommended(self):
        return RECOMMENDED in self.label

    @property
    def annotated(self):
        return self.concern is not None and self.raises is not None and self.addresses is not None

    def tags(self):
        return [t for t, _ in (self.raises or []) + (self.addresses or [])]

    def render(self):
        return "- " + ("<sel> " if self.sel else "") + ("* " if self.predicted else "") + self.body


@dataclass
class Record:
    number: int
    line: int                 # index of the `## Q<n>` heading
    end: int                  # index after the record's last non-blank line
    question: str = None
    marks: list = field(default_factory=list)
    meta: dict = field(default_factory=dict)
    meta_raw: str = None
    choices: list = field(default_factory=list)
    fields: dict = field(default_factory=dict)

    @property
    def by(self):
        return self.meta.get("by")

    @property
    def multi(self):
        return self.meta.get("select") == "multi"

    @property
    def declined(self):
        return self.fields.get("answer") == DECLINED

    def selected(self):
        return [c for c in self.choices if c.sel]

    def predicted(self):
        return [c for c in self.choices if c.predicted]

    def choice(self, label):
        return next((c for c in self.choices if c.label == label), None)

    def annotated(self):
        return all(c.annotated for c in self.choices)


@dataclass
class Concern:
    cid: int
    name: str
    line: int
    end: int
    meaning: str = None
    tags: list = field(default_factory=list)
    tags_line: int = None
    ratings: list = field(default_factory=list)   # (value, by, date), in file order

    @property
    def title(self):
        return f"C{self.cid} {self.name}"

    def rating(self, by):
        values = [v for v, who, _ in self.ratings if who == by]
        return values[-1] if values else None


@dataclass
class State:
    store: str
    problems: Problems
    log: list
    log_lines: list           # None when the log does not exist yet
    concerns: list
    weights_lines: list
    draft: list               # None when there is no round
    draft_lines: list
    exempt: list              # Exempt entries, in file order
    exempt_lines: list        # None when exempt.md does not exist

    def path(self, name):
        return os.path.join(self.store, name)


DIGITS = re.compile(r"[0-9]+")


def fmt(x):
    x = round(x, 2)
    return str(int(x)) if x == int(x) else f"{x:g}"


def read_lines(path):
    with open(path, encoding="utf-8", errors="surrogateescape", newline="") as fh:
        return fh.read().splitlines(keepends=True)


def newline_of(lines):
    return "\r\n" if lines and lines[0].endswith("\r\n") else "\n"


def write(path, text):
    """Write through a temporary file in the same folder, then rename over the target."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(path)), prefix=".tmp-", suffix=".md")
    try:
        try:
            mode = os.stat(path).st_mode & 0o7777
        except FileNotFoundError:
            umask = os.umask(0)
            os.umask(umask)
            mode = 0o666 & ~umask
        os.chmod(tmp, mode)
        with os.fdopen(fd, "w", encoding="utf-8", errors="surrogateescape", newline="") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def store_for(cwd):
    """`.question-refiner/` at the git root of cwd, or in cwd outside a repository."""
    return os.path.join(git_root(cwd) or os.path.abspath(cwd), STORE)


def store_of(args):
    return os.path.abspath(args.dir) if getattr(args, "dir", None) else store_for(os.getcwd())


def git_root(folder):
    try:
        return subprocess.run(["git", "-C", folder, "rev-parse", "--show-toplevel"], capture_output=True,
                              text=True).stdout.strip()
    except OSError:
        return ""


def project_of(store):
    """The folder whose skel 3.1.0 data belongs with this store: the git root holding it, else its parent."""
    parent = near = os.path.dirname(store)
    while not os.path.isdir(near) and os.path.dirname(near) != near:
        near = os.path.dirname(near)
    return git_root(near) or parent

def legacy_folders(root):
    """Folders under root holding skel 3.1.0 interview files that were neither imported nor set aside.

    In a git repository, every file git lists (tracked, or untracked and not ignored). Outside one, only root and
    root/skel, where skel 3.1.0 kept them: walking an arbitrary folder is slow and reaches into other repositories.
    """
    names = (LEGACY_LOG, LEGACY_WEIGHTS)
    paths = None
    try:
        out = subprocess.run(["git", "-C", root, "ls-files", "-z", "--cached", "--others", "--exclude-standard",
                              "--", *(f":(glob)**/{name}" for name in names)], capture_output=True, text=True)
        if out.returncode == 0:
            paths = [p for p in out.stdout.split("\0") if p]
    except OSError:
        pass
    if paths is None:
        paths = [os.path.join(folder, name) for folder in ("", "skel") for name in names
                 if os.path.isfile(os.path.join(root, folder, name))]
    found = {os.path.dirname(p) or "." for p in paths if os.path.basename(p) in names}
    return sorted(f for f in found if not os.path.exists(os.path.join(root, f, MOVED)))


def legacy_summary(folder):
    """(records in the legacy log, people with ratings in the legacy weights)."""
    def lines(name):
        path = os.path.join(folder, name)
        return [line.rstrip("\r\n") for line in read_lines(path)] if os.path.exists(path) else []
    records = sum(1 for t in lines(LEGACY_LOG) if RECORD_RE.match(t))
    raters = {m.group(2) for t in lines(LEGACY_WEIGHTS) if t.startswith("rating: ")
              for m in [RATING_RE.match(t[len("rating: "):])] if m}
    return records, len(raters)


def moved_note(text):
    return f"# Moved\n\n{text}\n"


def first_line(texts):
    return next((k for k, t in enumerate(texts) if t.strip()), None)


def split_marks(text, path, k, problems):
    marks = []
    for mark in MARK_ORDER:
        if text.startswith(f"<{mark}> "):
            marks.append(mark)
            text = text[len(mark) + 3:]
    if re.match(r"^<[a-z]+> ", text):
        problems.error(path, k + 1, "only `<probe>` then `<tracer>` may go before the question")
    if not text.strip():
        problems.error(path, k + 1, "the question text is empty")
    return text, marks


def parse_meta(text, path, k, problems):
    meta = {}
    for part in text.split(SEP):
        key, sep, value = part.partition(": ")
        if not sep or key not in META_KEYS:
            problems.error(path, k + 1, f"the meta line is `key: value` parts joined by ` · `, with keys "
                                        f"{', '.join(META_KEYS)}: {part}")
        elif key in meta:
            problems.error(path, k + 1, f"`{key}:` appears twice on the meta line")
        else:
            meta[key] = value.strip()
    if meta.get("select", "single") not in ("single", "multi"):
        problems.error(path, k + 1, "`select:` is `single` or `multi`")
    return meta


def annotate(choice, name, value, path, k, problems):
    if any(n == name for n, _ in choice.annotations):
        problems.error(path, k + 1, f"`{name}:` appears twice under one choice")
        return
    choice.annotations.append((name, value))
    if name == "concern":
        choice.concern = value
        return
    pairs = []
    if value.strip() != "none":
        for part in value.split(","):
            m = PAIR_RE.match(part.strip())
            if not m or not TAG_RE.match(m.group(1)):
                problems.error(path, k + 1, f"`{name}:` takes `<tag> <1-3>` pairs separated by commas, "
                                            f"or `none`: {part.strip()}")
                continue
            pairs.append((m.group(1), int(m.group(2))))
    setattr(choice, name, pairs)


def parse_records(path, lines, title, problems):
    texts = [line.rstrip("\r\n") for line in lines]
    start = first_line(texts)
    if start is None or texts[start] != title:
        problems.error(path, (start or 0) + 1, f"the file must start with `{title}`")
    records, rec, choice = [], None, None
    for k, t in enumerate(texts):
        if k == start or not t.strip():
            continue
        m = RECORD_RE.match(t)
        if m:
            rec, choice = Record(int(m.group(1)), k, k + 1), None
            records.append(rec)
            continue
        if rec is None:
            problems.error(path, k + 1, "text before the first `## Q<n>` record")
            continue
        rec.end = k + 1
        if rec.question is None:
            rec.question, rec.marks = split_marks(t, path, k, problems)
            continue
        m = CHOICE_RE.match(t)
        if m:
            body = t[2 + len(m.group(1) or "") + len(m.group(2) or ""):]
            choice = Choice(body=body, label=m.group(3), sel=bool(m.group(1)), predicted=bool(m.group(2)), line=k)
            rec.choices.append(choice)
            continue
        m = ANNOTATION_RE.match(t)
        if m:
            if choice is None:
                problems.error(path, k + 1, "an annotation line must follow a choice")
            else:
                annotate(choice, m.group(1), m.group(2), path, k, problems)
            continue
        m = FIELD_RE.match(t)
        if m:
            if m.group(1) in rec.fields:
                problems.error(path, k + 1, f"`{m.group(1)}:` appears twice in Q{rec.number}")
            rec.fields[m.group(1)] = m.group(2)
            choice = None
            continue
        if rec.meta_raw is None and not rec.choices:
            rec.meta_raw = t
            rec.meta = parse_meta(t, path, k, problems)
            continue
        hint = "; choice marks go `<sel>` then `*`" if t.startswith("- ") else ""
        problems.error(path, k + 1, f"not a recognised line{hint}: {t[:60]}")
    return records


def validate_records(path, records, problems, log):
    for i, rec in enumerate(records):
        at = rec.line + 1
        if rec.number != i + 1:
            problems.error(path, at, f"records are numbered in order from Q1; expected Q{i + 1}")
        if rec.question is None:
            problems.error(path, at, f"Q{rec.number} has no question line")
            continue
        need = META_KEYS if log else ("header", "select")
        missing = [key for key in need if key not in rec.meta]
        if missing:
            problems.error(path, at, f"Q{rec.number}: the meta line needs {', '.join(missing)}")
        if log and "round" in rec.meta and not DIGITS.fullmatch(rec.meta["round"]):
            problems.error(path, at, f"Q{rec.number}: `round:` is a number")
        if log and "asked" in rec.meta:
            try:
                datetime.datetime.strptime(rec.meta["asked"], STAMP_FORMAT)
            except ValueError:
                problems.error(path, at, f"Q{rec.number}: `asked:` is `YYYY-MM-DD HH:MM:SS ±ZZZZ`")
        offered = [c for c in rec.choices if c.label != "Other"]
        if len(offered) < 2:
            problems.error(path, at, f"Q{rec.number} needs at least 2 choices")
        if len(offered) > 4:
            problems.error(path, at, f"Q{rec.number} offers at most 4 choices, \"Other\" aside")
        labels = [c.label for c in rec.choices]
        if len(set(labels)) != len(labels):
            problems.error(path, at, f"Q{rec.number}: two choices have the same label")
        for c in rec.choices:
            if " | " in c.label:
                problems.error(path, c.line + 1, f"Q{rec.number}: a label cannot contain ` | `: {c.label}")
        for c in rec.choices:
            names = {n for n, _ in c.annotations}
            if names and names != {"concern", "raises", "addresses"}:
                problems.error(path, c.line + 1, "a choice is annotated with all of concern:, raises: and "
                                                 "addresses:, or with none of them")
            elif names and c.raises == []:
                problems.error(path, c.line + 1, "every choice raises at least one concern")
            elif not names:
                problems.warn(path, c.line + 1, f"Q{rec.number}: choice `{c.label}` is not annotated")
        chosen = rec.selected()
        if not log:
            if chosen:
                problems.error(path, at, f"Q{rec.number}: a round is answered by `record`; remove <sel>")
            stale = ((["<tracer>"] if "tracer" in rec.marks else [])
                     + [f"{k}:" for k in ("answer", "axis") if k in rec.fields])
            if stale:
                problems.error(path, at, f"Q{rec.number}: only `record` writes {', '.join(stale)}; "
                                         f"remove it from the round")
        elif rec.declined and chosen:
            problems.error(path, at, f"Q{rec.number}: a declined question has no <sel>")
        elif not rec.declined and not chosen:
            problems.error(path, at, f"Q{rec.number}: an answered question marks its choice with <sel>")
        elif not rec.multi and len(chosen) > 1:
            problems.error(path, at, f"Q{rec.number}: a single-choice question has one <sel>")


def parse_weights(path, lines, problems):
    texts = [line.rstrip("\r\n") for line in lines]
    start = first_line(texts)
    if start is None or texts[start] != WEIGHTS_TITLE:
        problems.error(path, (start or 0) + 1, f"the file must start with `{WEIGHTS_TITLE}`")
    concerns, c = [], None
    for k, t in enumerate(texts):
        if k == start or not t.strip():
            continue
        m = CONCERN_RE.match(t)
        if m:
            c = Concern(int(m.group(1)), m.group(2).strip(), k, k + 1)
            concerns.append(c)
            continue
        if c is None and t.startswith("domains:"):
            for bad in (d for d in split_list(t[len("domains:"):]) if d not in DOMAINS):
                problems.error(path, k + 1, f"`{bad}` is not a domain: {', '.join(DOMAINS)}")
            continue
        if c is None:
            problems.error(path, k + 1, "text before the first `## C<n>` concern")
            continue
        c.end = k + 1
        key, sep, value = t.partition(": ")
        if sep and key == "meaning":
            c.meaning = value
        elif sep and key == "tags":
            c.tags_line = k
            c.tags = [x.strip() for x in value.split(",") if x.strip()]
            for bad in (x for x in c.tags if not TAG_RE.match(x)):
                problems.error(path, k + 1, f"`{bad}` is not a tag: lower case, digits and hyphens, "
                                            f"optionally after `NEW:`")
        elif sep and key == "rating":
            m = RATING_RE.match(value)
            if not m or not 0 <= float(m.group(1)) <= 10:
                problems.error(path, k + 1, "`rating:` is `<0-10> · by: <name> · <YYYY-MM-DD>`")
            else:
                c.ratings.append((float(m.group(1)), m.group(2), m.group(3)))
        else:
            problems.error(path, k + 1, f"not a recognised line: {t[:60]}")
    seen = {}
    for c in concerns:
        if c.meaning is None or not c.tags:
            problems.error(path, c.line + 1, f"{c.title} needs `meaning:` and `tags:` lines")
        for tag in c.tags:
            if tag in seen and seen[tag] != c.cid:
                problems.error(path, c.tags_line + 1, f"`{tag}` is in C{seen[tag]} and C{c.cid}; "
                                                      f"a tag belongs to one concern")
            seen.setdefault(tag, c.cid)
    ids = [c.cid for c in concerns]
    for cid in {x for x in ids if ids.count(x) > 1}:
        problems.error(path, 1, f"C{cid} is used for two concerns")
    return concerns


@dataclass
class Exempt:
    asked: datetime.datetime
    by: str
    question: str
    reason: str


def parse_exempt(path, lines, problems):
    texts = [line.rstrip("\r\n") for line in lines]
    start = first_line(texts)
    if start is None or texts[start] != EXEMPT_TITLE:
        problems.error(path, (start or 0) + 1, f"the file must start with `{EXEMPT_TITLE}`")
    out = []
    for k, t in enumerate(texts):
        if k == start or not t.strip():
            continue
        m = EXEMPT_RE.match(t)
        try:
            asked = datetime.datetime.strptime(m.group(1), STAMP_FORMAT) if m else None
        except ValueError:
            asked = None
        if asked is None:
            problems.error(path, k + 1, "an exempt line is `- <YYYY-MM-DD HH:MM:SS ±ZZZZ> · by: <name> · "
                                        "question: <text> · reason: <text>`")
            continue
        out.append(Exempt(asked, m.group(2), m.group(3), m.group(4)))
    return out


@dataclass
class Entry:
    name: str
    meaning: str = None
    tags: list = field(default_factory=list)
    domains: list = field(default_factory=list)


def split_list(value):
    return [x.strip() for x in value.split(",") if x.strip()]


def catalog():
    """The concerns `domains add` copies from, in order."""
    entries, e = [], None
    for line in read_lines(CATALOG):
        t = line.rstrip("\r\n")
        if t.startswith("## "):
            e = Entry(t[3:].strip())
            entries.append(e)
        elif e is not None:
            key, sep, value = t.partition(": ")
            if sep and key == "meaning":
                e.meaning = value
            elif sep and key in ("tags", "domains"):
                setattr(e, key, split_list(value))
    return entries


def weights_domains(lines):
    for line in lines or []:
        t = line.rstrip("\r\n")
        if t.startswith("domains:"):
            return split_list(t[len("domains:"):])
    return []


def concern_lines(cid, e, nl, extra=()):
    return [nl, f"## C{cid} {e.name}{nl}", f"meaning: {e.meaning}{nl}",
            f"tags: {', '.join(list(e.tags) + list(extra))}{nl}"]


def tag_map(concerns):
    return {t: c for c in concerns for t in c.tags}


def stated(concerns, by):
    return {c.cid: c.rating(by) for c in concerns if c.rating(by) is not None}


def vector(choice, tags):
    """Net severity per concern: what the choice addresses minus what it raises."""
    v = {}
    for tag, severity in choice.addresses:
        cid = tags[tag].cid
        v[cid] = v.get(cid, 0) + severity
    for tag, severity in choice.raises:
        cid = tags[tag].cid
        v[cid] = v.get(cid, 0) - severity
    return v


def score(v, w):
    return sum(w.get(cid, 0.0) * x for cid, x in v.items())


def choose(rec, vectors, w, w_rec=0.0):
    scores = [score(v, w) + (w_rec if c.recommended else 0.0) for c, v in zip(rec.choices, vectors)]
    order = sorted(range(len(scores)), key=lambda i: (-scores[i], not rec.choices[i].recommended, i))
    if rec.multi:
        picked = [i for i, s in enumerate(scores) if s > 0] or [order[0]]
        gap = min(abs(s) for s in scores)
    else:
        picked = [order[0]]
        gap = scores[order[0]] - scores[order[1]] if len(order) > 1 else 0.0
    return picked, scores, gap


def axis(v_to, v_from):
    """(concern gained most, concern lost most) going from one choice to another, or None."""
    d = {cid: v_to.get(cid, 0) - v_from.get(cid, 0) for cid in sorted(set(v_to) | set(v_from))}
    if not d:
        return None
    gain = max(d, key=lambda cid: d[cid])
    loss = min(d, key=lambda cid: d[cid])
    return (gain, loss) if d[gain] > 0 and d[loss] < 0 else None


def axis_text(a, by_id):
    return f"{by_id[a[0]].title} vs {by_id[a[1]].title}"


def parse_axis(text):
    m = AXIS_RE.match(text or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


def tracers(log, by):
    return [r for r in log if r.by == by and "tracer" in r.marks]


def dissent(log, by):
    """Each unordered axis over this person's tracers, with how many tracers it has."""
    return Counter(frozenset(a) for a in (parse_axis(r.fields.get("axis")) for r in tracers(log, by)) if a)


def probe_axis(vectors, counts):
    best, best_count = None, 0
    for i in range(len(vectors)):
        for j in range(i + 1, len(vectors)):
            a = axis(vectors[i], vectors[j])
            if a and counts.get(frozenset(a), 0) > best_count:
                best, best_count = a, counts[frozenset(a)]
    return best


def fit_data(log, tags, by):
    data = []
    for rec in log:
        if rec.by != by or rec.multi or rec.declined or not rec.annotated() or len(rec.selected()) != 1:
            continue
        if any(t not in tags for c in rec.choices for t in c.tags()):
            continue
        vecs = [vector(c, tags) for c in rec.choices]
        recs = [1.0 if c.recommended else 0.0 for c in rec.choices]
        data.append((vecs, recs, rec.choices.index(rec.selected()[0])))
    return data


def fit(data, w0):
    """Gradient ascent on the softmax log-likelihood, pulled toward the stated weights (and w_rec toward 0)."""
    cids = sorted(w0)
    w, w_rec = dict(w0), 0.0
    rate = RATE / max(1, len(data))
    for _ in range(STEPS):
        gw = {c: -2 * LAMBDA * (w[c] - w0[c]) for c in cids}
        grec = -2 * LAMBDA * w_rec
        for vecs, recs, s in data:
            u = [T * (score(v, w) + w_rec * r) for v, r in zip(vecs, recs)]
            top = max(u)
            e = [math.exp(x - top) for x in u]
            z = sum(e)
            p = [x / z for x in e]
            # Vectors are sparse (a choice touches a few concerns), so only their entries are visited.
            for c, x in vecs[s].items():
                if c in gw:
                    gw[c] += T * x
            for pj, v in zip(p, vecs):
                for c, x in v.items():
                    if c in gw:
                        gw[c] -= T * pj * x
            grec += T * (recs[s] - sum(pj * r for pj, r in zip(p, recs)))
        for c in cids:
            w[c] = min(10.0, max(0.0, w[c] + rate * gw[c]))
        w_rec = min(10.0, max(-10.0, w_rec + rate * grec))
    return w, w_rec


def overfit(w, w0, log, by):
    """Concerns a fit drove to a bound, far from the stated rating, on two tracers or fewer."""
    counts = Counter()
    for rec in tracers(log, by):
        a = parse_axis(rec.fields.get("axis"))
        if a:
            counts.update(set(a))
    return [c for c in sorted(w) if (w[c] <= 0.0 or w[c] >= 10.0) and abs(w[c] - w0[c]) > 3 and counts[c] <= 2]


def weights_for(state, by):
    """The weights to predict with, w_rec, the model name and the person's tracer count."""
    w0 = stated(state.concerns, by)
    n = len(tracers(state.log, by))
    if n < MIN_TRACERS:
        return w0, 0.0, "stated", n
    w, w_rec = fit(fit_data(state.log, tag_map(state.concerns), by), w0)
    return w, w_rec, "fitted+rec", n


def hit_rows(log, by):
    rows = []
    for rec in log:
        sel = {c.label for c in rec.selected()}
        if rec.by != by or rec.declined or "prediction" not in rec.fields or not sel:
            continue
        shown = {c.label for c in rec.predicted()}
        only = set(rec.fields.get("concern-only", "").split(" | "))
        rows.append((int(rec.meta["round"]), shown == sel, only == sel))
    return rows


def load(store):
    problems = Problems()

    def lines_of(name):
        path = os.path.join(store, name)
        return read_lines(path) if os.path.exists(path) else None

    log_lines, weights_lines, draft_lines = lines_of(LOG), lines_of(WEIGHTS), lines_of(DRAFT)
    exempt_lines = lines_of(EXEMPT)
    exempt = parse_exempt(os.path.join(store, EXEMPT), exempt_lines, problems) if exempt_lines is not None else []
    log = []
    if log_lines is not None:
        log = parse_records(os.path.join(store, LOG), log_lines, LOG_TITLE, problems)
        validate_records(os.path.join(store, LOG), log, problems, log=True)
    concerns = []
    if weights_lines is not None:
        concerns = parse_weights(os.path.join(store, WEIGHTS), weights_lines, problems)
    draft = None
    if draft_lines is not None:
        draft = parse_records(os.path.join(store, DRAFT), draft_lines, DRAFT_TITLE, problems)
        validate_records(os.path.join(store, DRAFT), draft, problems, log=False)
    tags = tag_map(concerns)
    for name, recs in ((LOG, log), (DRAFT, draft or [])):
        for rec in recs:
            for c in rec.choices:
                for tag in c.tags():
                    if tag not in tags:
                        problems.warn(os.path.join(store, name), c.line + 1,
                                      f"tag `{tag}` belongs to no concern; map it with `refiner.py tag`")
    return State(store, problems, log, log_lines, concerns, weights_lines, draft, draft_lines, exempt, exempt_lines)


def render_record(rec, nl):
    out = [f"## Q{rec.number}", "".join(f"<{m}> " for m in MARK_ORDER if m in rec.marks) + rec.question]
    if rec.meta_raw is not None:
        out.append(rec.meta_raw)
    for c in rec.choices:
        out.append(c.render())
        out += [f"    {name}: {value}" for name, value in c.annotations]
    out += [f"{name}: {rec.fields[name]}" for name in FIELD_ORDER if name in rec.fields]
    return [line + nl for line in out]


def rebuild(lines, records):
    """The file with each record rendered again and every line between records kept as it was."""
    if not records:
        return "".join(lines)
    nl = newline_of(lines)
    out = list(lines[:records[0].line])
    for i, rec in enumerate(records):
        out += render_record(rec, nl)
        nxt = records[i + 1].line if i + 1 < len(records) else len(lines)
        out += lines[rec.end:nxt]
    return "".join(out)


def checked(path, text):
    """The text, if it parses cleanly as the file it is about to replace; otherwise exit and write nothing."""
    problems = Problems()
    lines = text.splitlines(keepends=True)
    name = os.path.basename(path)
    if name == EXEMPT:
        parse_exempt(path, lines, problems)
    elif name == WEIGHTS:
        parse_weights(path, lines, problems)
    else:
        log = name == LOG
        recs = parse_records(path, lines, LOG_TITLE if log else DRAFT_TITLE, problems)
        validate_records(path, recs, problems, log=log)
    if problems.errors:
        sys.exit("\n".join(["nothing written: the result would not parse"] + problems.errors))
    return text


def fail_on_errors(state):
    if state.problems.errors:
        for line in state.problems.errors:
            print(line, file=sys.stderr)
        sys.exit("fix these first (`refiner.py parse` lists them)")


def need_weights(state):
    if state.weights_lines is None:
        sys.exit(f"no {WEIGHTS} yet: choose the domains with `refiner.py domains add DOMAIN ...` "
                 f"({', '.join(DOMAINS)})")


def check_name(name, what):
    if not name.strip() or "\n" in name or "\r" in name or SEP in f" {name} ":
        sys.exit(f"{what} must be one line, not empty, and without `{SEP.strip()}` between spaces or at either end: "
                 f"{name!r}")
    return name


def person(args):
    if getattr(args, "by", None):
        return check_name(args.by, "--by")
    try:
        name = subprocess.run(["git", "config", "user.name"], capture_output=True, text=True,
                              cwd=os.path.dirname(store_of(args))).stdout.strip()
    except OSError:
        name = ""
    if not name:
        sys.exit("no --by given and `git config user.name` is not set; pass --by NAME")
    return check_name(name, "`git config user.name`")


def relevant(state, by):
    """The records whose concerns matter for this person: their own history and the round being asked."""
    return [r for r in state.log if r.by == by] + (state.draft or [])


def used_concerns(state, records):
    tags = tag_map(state.concerns)
    unmapped, used = set(), set()
    for rec in records:
        for c in rec.choices:
            for tag in c.tags():
                if tag in tags:
                    used.add(tags[tag].cid)
                else:
                    unmapped.add(tag)
    return unmapped, used


def line_end(line, nl):
    return line[len(line.rstrip("\r\n")):] or nl


def cmd_import(args):
    store = store_of(args)
    src = os.path.abspath(args.source)
    state = load(store)
    if state.log_lines is not None or state.weights_lines is not None:
        sys.exit(f"{store} already has {LOG} or {WEIGHTS}: import only into an empty store, so two histories are "
                 f"never merged")
    if state.draft_lines is not None:
        sys.exit(f"{store} already has {DRAFT}: record or delete that round first, so import does not replace it")
    found = [name for name in LEGACY if os.path.exists(os.path.join(src, name))]
    if LEGACY_LOG not in found and LEGACY_WEIGHTS not in found:
        sys.exit(f"no skel 3.1.0 interview files ({LEGACY_LOG}, {LEGACY_WEIGHTS}) in {src}")
    out = {}
    for name in found:
        old_title, new_name, new_title = LEGACY[name]
        lines = read_lines(os.path.join(src, name))
        texts = [line.rstrip("\r\n") for line in lines]
        k = first_line(texts)
        if k is None or texts[k] != old_title:
            sys.exit(f"{name} does not start with `{old_title}`; nothing imported")
        nl = newline_of(lines)
        lines[k] = new_title + line_end(lines[k], nl)
        if name == LEGACY_WEIGHTS:
            lines[k + 1:k + 1] = [nl, f"domains: software{nl}"]
        path = os.path.join(store, new_name)
        out[path] = checked(path, "".join(lines))
    skipped = stale_round(out, store)
    if skipped:
        del out[os.path.join(store, DRAFT)]
    for path, text in out.items():
        write(path, text)
    today = datetime.date.today().isoformat()
    write(os.path.join(src, MOVED), moved_note(f"These files moved to {STORE}/ on {today} (refiner.py import). "
                                                f"They are no longer updated."))
    for name in found:
        if name == LEGACY_DRAFT and skipped:
            print(f"{os.path.join(src, name)}: not copied, its round is already recorded")
        else:
            print(f"{os.path.join(src, name)} -> {os.path.join(store, LEGACY[name][1])}")
    return 0


def stale_round(out, store):
    """True when the round being imported is already in the log being imported (skel left its draft behind)."""
    log, draft = (out.get(os.path.join(store, name)) for name in (LOG, DRAFT))
    if log is None or draft is None:
        return False
    logged = parse_records(LOG, log.splitlines(keepends=True), LOG_TITLE, Problems())
    rounds = parse_records(DRAFT, draft.splitlines(keepends=True), DRAFT_TITLE, Problems())
    ids = {r.fields.get("round-id") for r in logged} - {None}
    return any(r.fields.get("round-id") in ids for r in rounds)


def cmd_concerns(args):
    state = load(store_of(args))
    fail_on_errors(state)
    need_weights(state)
    by = person(args)
    unmapped, used = used_concerns(state, relevant(state, by))
    rated = stated(state.concerns, by)
    unrated = [c for c in state.concerns if c.cid in used and c.cid not in rated]
    have = {c.name for c in state.concerns}
    hints = {}
    for tag in unmapped:
        bare = tag[len("NEW:"):] if tag.startswith("NEW:") else tag
        e = next((e for e in catalog() if bare in e.tags and e.name not in have), None)
        if e is not None:
            hints[tag] = e.name
    if args.json:
        print(json.dumps({"by": by, "unmapped": sorted(unmapped), "catalog": hints,
                          "unrated": [{"id": c.cid, "name": c.name, "meaning": c.meaning} for c in unrated]}))
        return 0
    if unmapped:
        print("Tags with no concern (map each with `refiner.py tag`):")
        for tag in sorted(unmapped):
            hint = f"  (catalog: {hints[tag]}; `refiner.py tag {tag} --catalog`)" if tag in hints else ""
            print(f"  {tag}{hint}")
    if unrated:
        print(f"Concerns {by} has not rated (rate them with `refiner.py rate`):")
        for c in unrated:
            print(f"  {c.title}: {c.meaning}")
    if not unmapped and not unrated:
        print(f"Nothing to map or rate for {by}.")
    return 0


def cmd_domains(args):
    state = load(store_of(args))
    entries = catalog()
    if args.action is None:
        print("Domains in use: " + (", ".join(weights_domains(state.weights_lines)) or "none"))
        for d in DOMAINS:
            print(f"  {d}: {sum(d in e.domains for e in entries)} concerns")
        return 0
    fail_on_errors(state)
    bad = [d for d in args.names if d not in DOMAINS]
    if bad or not args.names:
        sys.exit(f"name domains from: {', '.join(DOMAINS)}" + (f"; not {', '.join(bad)}" if bad else ""))
    root = project_of(store_of(args))
    legacy = legacy_folders(root) if state.weights_lines is None else []
    if legacy and not args.fresh:
        sys.exit(f"skel 3.1.0 interview data has not been moved: {', '.join(legacy)}. Move it with "
                 f"`refiner.py import \"{os.path.normpath(os.path.join(root, legacy[0]))}\"`, or start fresh with "
                 f"`refiner.py domains add ... --fresh`")
    for folder in legacy:
        write(os.path.join(root, folder, MOVED),
              moved_note(f"Not imported: a fresh start was chosen on {datetime.date.today().isoformat()} "
                         f"(refiner.py domains add --fresh)."))
    path = state.path(WEIGHTS)
    lines = [WEIGHTS_TITLE + "\n", "\n", "domains:\n"] if state.weights_lines is None else list(state.weights_lines)
    nl = newline_of(lines)
    texts = [line.rstrip("\r\n") for line in lines]
    k = next((i for i, t in enumerate(texts) if t.startswith("domains:")), None)
    if k is None:
        k = first_line(texts) + 1
        lines[k:k] = [nl, ""]
        k += 1
    used = weights_domains(lines)
    want = used + [d for d in args.names if d not in used]
    lines[k] = f"domains: {', '.join(want)}{nl}"
    have = {c.name for c in state.concerns}
    taken = set(tag_map(state.concerns))
    cid = max((c.cid for c in state.concerns), default=0)
    added, skipped = [], []
    for e in entries:
        if e.name in have or not set(e.domains) & set(want):
            continue
        if set(e.tags) & taken:
            skipped.append(e.name)
            continue
        cid += 1
        if not lines[-1].endswith(("\n", "\r")):
            lines[-1] += nl
        lines += concern_lines(cid, e, nl)
        added.append(f"C{cid} {e.name}")
    write(path, checked(path, "".join(lines)))
    print(f"Domains: {', '.join(want)}")
    print("Added: " + (", ".join(added) or "nothing"))
    if skipped:
        print("Not added, a tag is already in use: " + ", ".join(skipped))
    return 0


def cmd_tag(args):
    state = load(store_of(args))
    fail_on_errors(state)
    need_weights(state)
    tag = args.tag
    if not TAG_RE.match(tag):
        sys.exit(f"`{tag}` is not a tag: lower case, digits and hyphens, optionally after `NEW:`")
    if bool(args.concern) + bool(args.new) + bool(args.catalog) != 1:
        sys.exit("give one of a concern (`C<n>`), `--new NAME MEANING` or `--catalog`")
    tags = tag_map(state.concerns)
    if tag in tags:
        sys.exit(f"`{tag}` already belongs to {tags[tag].title}; a tag belongs to one concern")
    lines = list(state.weights_lines)
    nl = newline_of(lines)
    if args.new:
        name, meaning = (check_name(x, "--new NAME and MEANING") for x in args.new)
        cid = max((c.cid for c in state.concerns), default=0) + 1
        if lines and not lines[-1].endswith(("\n", "\r")):
            lines[-1] += nl
        lines += [nl, f"## C{cid} {name}{nl}", f"meaning: {meaning}{nl}", f"tags: {tag}{nl}"]
        title = f"C{cid} {name}"
    elif args.catalog:
        bare = tag[len("NEW:"):] if tag.startswith("NEW:") else tag
        e = next((e for e in catalog() if bare in e.tags), None)
        if e is None:
            sys.exit(f"no catalog concern has the tag `{bare}`")
        have = next((c for c in state.concerns if c.name == e.name), None)
        if have is not None:
            sys.exit(f"{e.name} is already {have.title}: run `refiner.py tag {tag} C{have.cid}`")
        clash = [t for t in e.tags if t in tags]
        if clash:
            sys.exit(f"`{clash[0]}` already belongs to {tags[clash[0]].title}")
        cid = max((c.cid for c in state.concerns), default=0) + 1
        if lines and not lines[-1].endswith(("\n", "\r")):
            lines[-1] += nl
        lines += concern_lines(cid, e, nl, extra=[tag] if tag != bare else [])
        title = f"C{cid} {e.name}"
    else:
        m = re.match(r"^C(\d+)$", args.concern)
        concern = next((c for c in state.concerns if m and c.cid == int(m.group(1))), None)
        if concern is None:
            sys.exit(f"no concern {args.concern} in {WEIGHTS}")
        k = concern.tags_line
        lines[k] = "tags: " + ", ".join(concern.tags + [tag]) + line_end(lines[k], nl)
        title = concern.title
    write(state.path(WEIGHTS), checked(state.path(WEIGHTS), "".join(lines)))
    print(f"`{tag}` belongs to {title}")
    return 0


def cmd_rate(args):
    state = load(store_of(args))
    fail_on_errors(state)
    need_weights(state)
    by = person(args)
    date = args.date or datetime.date.today().isoformat()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
        sys.exit("--date is YYYY-MM-DD")
    by_id = {c.cid: c for c in state.concerns}
    ratings, errors = [], []
    for item in args.ratings:
        m = re.match(r"^C(\d+)=(\d+(?:\.\d+)?)$", item)
        if not m:
            errors.append(f"a rating is `C<n>=<0-10>`: {item}")
        elif int(m.group(1)) not in by_id:
            errors.append(f"no concern C{m.group(1)} in {WEIGHTS}")
        elif not 0 <= float(m.group(2)) <= 10:
            errors.append(f"a rating is from 0 to 10: {item}")
        elif any(c.cid == int(m.group(1)) for c, _ in ratings):
            errors.append(f"C{m.group(1)} is rated twice")
        else:
            ratings.append((by_id[int(m.group(1))], float(m.group(2))))
    if errors:
        sys.exit("\n".join(errors))
    lines = list(state.weights_lines)
    nl = newline_of(lines)
    for concern, value in sorted(ratings, key=lambda r: -r[0].end):
        at = concern.end
        if not lines[at - 1].endswith(("\n", "\r")):
            lines[at - 1] += nl
        lines.insert(at, f"rating: {fmt(value)} · by: {by} · {date}{nl}")
    write(state.path(WEIGHTS), checked(state.path(WEIGHTS), "".join(lines)))
    for concern, value in ratings:
        print(f"{concern.title}: {fmt(value)} ({by})")
    return 0


def readiness(state, by):
    errors = []
    unmapped, used = used_concerns(state, relevant(state, by))
    errors += [f"tag `{t}` belongs to no concern: run `refiner.py tag {t} C<n>` "
               f"or `--new NAME MEANING`" for t in sorted(unmapped)]
    rated = stated(state.concerns, by)
    by_id = {c.cid: c for c in state.concerns}
    errors += [f"{by_id[cid].title} is not rated by {by}: run `refiner.py rate C{cid}=<0-10>`"
               for cid in sorted(used - set(rated))]
    return errors


def cmd_predict(args):
    state = load(store_of(args))
    fail_on_errors(state)
    need_weights(state)
    by = person(args)
    if state.draft is None:
        sys.exit(f"no round to predict: write {DRAFT} first")
    errors = []
    for rec in state.draft:
        for c in rec.choices:
            if not c.annotated:
                errors.append(f"Q{rec.number}: choice `{c.label}` is not annotated")
            if c.label == "Other":
                errors.append(f"Q{rec.number}: `Other` is added after predict, when the answer is typed")
    errors += readiness(state, by)
    if errors:
        sys.exit("\n".join(errors))
    w, w_rec, model, n = weights_for(state, by)
    rated = stated(state.concerns, by)
    tags = tag_map(state.concerns)
    by_id = {c.cid: c for c in state.concerns}
    counts = dissent(state.log, by)
    ids = [r.fields["round-id"] for r in state.draft if "round-id" in r.fields]
    round_id = ids[0] if ids else secrets.token_hex(4)
    for rec in state.draft:
        vecs = [vector(c, tags) for c in rec.choices]
        picked, scores, gap = choose(rec, vecs, w, w_rec)
        only, _, _ = choose(rec, vecs, rated)
        for i, c in enumerate(rec.choices):
            c.predicted = i in picked
        labels = " | ".join(rec.choices[i].label for i in picked)
        rec.fields["prediction"] = (f"{labels} · score {fmt(max(scores[i] for i in picked))} · "
                                    f"gap {fmt(gap)} · model: {model}")
        rec.fields["concern-only"] = " | ".join(rec.choices[i].label for i in only)
        rec.meta["by"] = by
        rec.fields["round-id"] = round_id
        rec.meta_raw = SEP.join(f"{key}: {rec.meta[key]}" for key in META_KEYS if key in rec.meta)
        rec.marks = [m for m in rec.marks if m != "probe"]
        rec.fields.pop("probes", None)
        a = probe_axis(vecs, counts)
        if a:
            rec.marks.insert(0, "probe")
            rec.fields["probes"] = axis_text(a, by_id)
        print(f"Q{rec.number}: {labels} (lead {fmt(gap)})" + (f", probe: {rec.fields['probes']}" if a else ""))
    print(f"model: {model} ({n} tracers; {MIN_TRACERS} needed to fit)")
    write(state.path(DRAFT), checked(state.path(DRAFT), rebuild(state.draft_lines, state.draft)))
    return 0


ANSWER_RE = re.compile(r"^Q([0-9]+)=(.+)$")


def parse_answers(text):
    answers = {}
    for part in (p.strip() for p in text.split(",")):
        if not part:
            continue
        m = ANSWER_RE.match(part.replace(" ", ""))
        if not m:
            raise ValueError(f"an answer is `Q<n>=<choice>`, `Q<n>=Other` or `Q<n>=none`: {part}")
        n = int(m.group(1))
        if n in answers:
            raise ValueError(f"Q{n} is answered twice")
        answers[n] = [t.lower() for t in m.group(2).split("+")]
    return answers


def answer_errors(rec, tokens, tags, by):
    errors = []
    offered = [c for c in rec.choices if c.label != "Other"]
    other = rec.choice("Other")
    if "prediction" not in rec.fields:
        errors.append(f"Q{rec.number} has no prediction: run `refiner.py predict` first")
    elif ("concern-only" not in rec.fields or "round-id" not in rec.fields or not rec.predicted()
          or any(rec.choice(label) is None for label in rec.fields["concern-only"].split(" | "))):
        errors.append(f"Q{rec.number}: its prediction does not match its choices; "
                      f"run `refiner.py predict` again, then ask it")
    elif rec.by != by:
        errors.append(f"Q{rec.number} was predicted for {rec.by}, not {by}; run `refiner.py predict --by {by}`")
    if tokens == ["none"]:
        return errors
    if "none" in tokens:
        errors.append(f"Q{rec.number}: `none` cannot be combined with choices")
    if len(tokens) > 1 and not rec.multi:
        errors.append(f"Q{rec.number} is single-choice: give one answer")
    for t in tokens:
        if t == "other":
            if other is None or not other.annotated:
                errors.append(f"Q{rec.number}: add the typed answer to the round as `- **Other**: <text>` with "
                              f"its concern:, raises: and addresses: lines, then record again")
            elif any(tag not in tags for tag in other.tags()):
                errors.append(f"Q{rec.number}: map the Other choice's tags with `refiner.py tag` first")
        elif DIGITS.fullmatch(t):
            if not 1 <= int(t) <= len(offered):
                errors.append(f"Q{rec.number}: choice {t} is out of range 1-{len(offered)}")
        elif t != "none":
            errors.append(f"Q{rec.number}={t}: an answer is a choice number, `Other` or `none`")
    if other is not None and "other" not in tokens:
        errors.append(f"Q{rec.number} has an Other choice, so its answer is Other")
    return errors


def now_stamp():
    return datetime.datetime.now().astimezone().strftime(STAMP_FORMAT)


def cmd_exempt(args):
    state = load(store_of(args))
    fail_on_errors(state)
    by = person(args)
    question = check_name(args.question.strip(), "--question")
    reason = check_name(args.reason.strip(), "--reason")
    if any(r.question.strip() == question for r in state.draft or []):
        sys.exit(f"`{question}` is in {DRAFT}: a question in the round is predicted and recorded, not exempted")
    asked = args.asked or now_stamp()
    try:
        datetime.datetime.strptime(asked, STAMP_FORMAT)
    except ValueError:
        sys.exit("--asked is `YYYY-MM-DD HH:MM:SS ±ZZZZ`")
    lines = list(state.exempt_lines) if state.exempt_lines is not None else [EXEMPT_TITLE + "\n", "\n"]
    nl = newline_of(lines)
    if not lines[-1].endswith(("\n", "\r")):
        lines[-1] += nl
    lines.append(f"- {asked} · by: {by} · question: {question} · reason: {reason}{nl}")
    write(state.path(EXEMPT), checked(state.path(EXEMPT), "".join(lines)))
    print(f"exempt: {question} ({reason})")
    return 0


def passable(state, now):
    """Questions the gate lets through: predicted in the round, or exempted in the last EXEMPT_WINDOW seconds."""
    ok = {r.question.strip() for r in state.draft or [] if "prediction" in r.fields}
    ok |= {e.question for e in state.exempt if 0 <= (now - e.asked).total_seconds() <= EXEMPT_WINDOW}
    return ok


def cmd_record(args):
    state = load(store_of(args))
    fail_on_errors(state)
    need_weights(state)
    by = person(args)
    if state.draft is None:
        sys.exit(f"no round to record: {DRAFT} does not exist")
    try:
        answers = parse_answers(args.answers)
    except ValueError as e:
        sys.exit(str(e))
    asked = args.asked or now_stamp()
    try:
        datetime.datetime.strptime(asked, STAMP_FORMAT)
    except ValueError:
        sys.exit("--asked is `YYYY-MM-DD HH:MM:SS ±ZZZZ`")
    tags = tag_map(state.concerns)
    numbers = {r.number for r in state.draft}
    errors = [f"Q{n} is not in the round" for n in sorted(set(answers) - numbers)]
    errors += [f"Q{n} has no answer; use Q{n}=none to record it as declined" for n in sorted(numbers - set(answers))]
    for rec in state.draft:
        if rec.number in answers:
            errors += answer_errors(rec, answers[rec.number], tags, by)
    logged = {r.fields.get("round-id") for r in state.log} - {None}
    if not errors and any(r.fields["round-id"] in logged for r in state.draft):
        errors.append(f"this round is already in {LOG}, so {DRAFT} was left behind: delete it")
    if errors:
        sys.exit("\n".join(errors))
    by_id = {c.cid: c for c in state.concerns}
    base = len(state.log)
    rnd = max((int(r.meta["round"]) for r in state.log), default=0) + 1
    for k, rec in enumerate(state.draft):
        tokens = answers[rec.number]
        offered = [c for c in rec.choices if c.label != "Other"]
        if tokens == ["none"]:
            rec.fields["answer"] = DECLINED
        else:
            for t in tokens:
                (rec.choice("Other") if t == "other" else offered[int(t) - 1]).sel = True
        rec.number = base + k + 1
        rec.meta.update({"round": str(rnd), "asked": asked, "by": by})
        rec.meta_raw = SEP.join(f"{key}: {rec.meta[key]}" for key in META_KEYS if key in rec.meta)
        if not rec.multi and not rec.declined:
            chosen, ref = rec.selected()[0], rec.choice(rec.fields["concern-only"])
            if ref is not None and chosen is not ref:
                rec.marks = [m for m in rec.marks if m != "tracer"] + ["tracer"]
                a = axis(vector(chosen, tags), vector(ref, tags))
                rec.fields["axis"] = axis_text(a, by_id) if a else "none"
    log_lines = state.log_lines if state.log_lines is not None else [LOG_TITLE + newline_of(state.draft_lines)]
    nl = newline_of(log_lines)
    text = "".join(log_lines)
    if not text.endswith(("\n", "\r")):
        text += nl
    for rec in state.draft:
        text += nl + "".join(render_record(rec, nl))
    write(state.path(LOG), checked(state.path(LOG), text))
    os.remove(state.path(DRAFT))
    hits = answered = 0
    for rec in state.draft:
        sel = {c.label for c in rec.selected()}
        shown = {c.label for c in rec.predicted()}
        answered += bool(sel)
        hits += bool(sel) and sel == shown
        note = f", tracer: {rec.fields['axis']}" if "tracer" in rec.marks else ""
        if not sel:
            answer = "declined"
        elif sel == shown:
            answer = " + ".join(sorted(sel)) + " (predicted)"
        else:
            answer = " + ".join(sorted(sel)) + f" (predicted: {' + '.join(sorted(shown))})"
        print(f"Q{rec.number}: {answer}{note}")
    print(f"round {rnd}: {hits} of {answered} predictions hit")
    return 0


def cmd_fit(args):
    state = load(store_of(args))
    fail_on_errors(state)
    need_weights(state)
    by = person(args)
    errors = readiness(state, by)
    if errors:
        sys.exit("\n".join(errors))
    w0 = stated(state.concerns, by)
    w, w_rec, model, n = weights_for(state, by)
    warn = overfit(w, w0, state.log, by) if model != "stated" else []
    by_id = {c.cid: c for c in state.concerns}
    if args.json:
        print(json.dumps({"by": by, "model": model, "tracers": n, "w_rec": round(w_rec, 3),
                          "concerns": [{"id": c, "name": by_id[c].name, "stated": w0[c], "fitted": round(w[c], 3)}
                                       for c in sorted(w0)],
                          "overfit": warn}))
        return 0
    if model == "stated":
        print(f"No fit for {by}: {n} tracers, {MIN_TRACERS} needed. Predictions use the stated ratings.")
        return 0
    print(f"Fitted weights for {by} ({n} tracers):")
    for c in sorted(w0):
        moved = "" if abs(w[c] - w0[c]) < 0.5 else "  (moved)"
        print(f"  {by_id[c].title}: stated {fmt(w0[c])}, fitted {fmt(w[c])}{moved}")
    print(f"  recommended choice (w_rec): {fmt(w_rec)}")
    for c in warn:
        print(f"warning: {by_id[c].title} reached {fmt(w[c])} on two tracers or fewer; "
              f"it may not be a real preference")
    return 0


def cmd_hits(args):
    state = load(store_of(args))
    fail_on_errors(state)
    need_weights(state)
    by = person(args)
    rows = hit_rows(state.log, by)
    rounds = sorted({r for r, _, _ in rows})
    per_round = [{"round": r, "shown": sum(s for x, s, _ in rows if x == r),
                  "stated": sum(o for x, _, o in rows if x == r), "total": sum(1 for x, _, _ in rows if x == r)}
                 for r in rounds]
    shown, only = sum(s for _, s, _ in rows), sum(o for _, _, o in rows)
    if args.json:
        print(json.dumps({"by": by, "shown": {"hits": shown, "total": len(rows)},
                          "stated": {"hits": only, "total": len(rows)}, "rounds": per_round}))
        return 0

    def pct(h, t):
        return f"{h} of {t}" + (f" ({round(100 * h / t)}%)" if t else "")

    print(f"Hit rates for {by}, from predictions logged before each answer:")
    print(f"  Shown predictions: {pct(shown, len(rows))}")
    print(f"  Stated ratings only: {pct(only, len(rows))}")
    for r in per_round[-5:]:
        print(f"  round {r['round']}: shown {r['shown']}/{r['total']}, stated {r['stated']}/{r['total']}")
    return 0


def cmd_parse(args):
    state = load(store_of(args))
    for line in state.problems.errors:
        print("error: " + line)
    for line in state.problems.warnings:
        print("warning: " + line)
    n = len(state.log)
    draft = f", round being asked: {len(state.draft)} questions" if state.draft is not None else ""
    no_weights = f" (no {WEIGHTS} yet: run `refiner.py domains add`)" if state.weights_lines is None else ""
    print(f"{n} record{'s' if n != 1 else ''}, {len(state.concerns)} concerns{no_weights}{draft}")
    return 1 if state.problems.errors else 0


COMMANDS = {"parse": cmd_parse, "domains": cmd_domains, "exempt": cmd_exempt, "import": cmd_import,
            "concerns": cmd_concerns, "tag": cmd_tag, "rate": cmd_rate, "predict": cmd_predict, "record": cmd_record,
            "fit": cmd_fit, "hits": cmd_hits}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def command(name, json_flag=False):
        p = sub.add_parser(name)
        p.add_argument("--dir", help="the store (default: .question-refiner/ at the git root)")
        p.add_argument("--by")
        if json_flag:
            p.add_argument("--json", action="store_true")
        return p

    command("parse")
    command("concerns", json_flag=True)
    p = command("domains")
    p.add_argument("action", nargs="?", choices=["add"])
    p.add_argument("names", nargs="*")
    p.add_argument("--fresh", action="store_true", help="start new weights although skel 3.1.0 data is not moved")
    p = command("tag")
    p.add_argument("--catalog", action="store_true")
    p.add_argument("tag")
    p.add_argument("concern", nargs="?")
    p.add_argument("--new", nargs=2, metavar=("NAME", "MEANING"))
    p = command("rate")
    p.add_argument("ratings", nargs="+")
    p.add_argument("--date")
    command("predict")
    p = command("record")
    p.add_argument("--answers", required=True)
    p.add_argument("--asked")
    p = command("exempt")
    p.add_argument("--question", required=True)
    p.add_argument("--reason", required=True)
    p.add_argument("--asked")
    p = command("import")
    p.add_argument("source", help="the folder holding skel 3.1.0's .interviews.md and .interview-weights.md")
    command("fit", json_flag=True)
    command("hits", json_flag=True)
    args = ap.parse_args(argv)
    return COMMANDS[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
