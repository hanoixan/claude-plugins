#!/usr/bin/env python3
"""Record skel interviews, rate the concerns behind them, and predict answers.

Files, all in SKEL_DIR (normally skel/):
  .interviews.md          every question asked: its choices, their annotations, the prediction and the answer
  .interview-weights.md   general concerns, the tags they cover, and each person's ratings
  .interview-round.md     the round being asked (git-ignored); deleted when the round is recorded

Commands (--by defaults to `git config user.name`):
  parse SKEL_DIR                                     validate the three files
  concerns SKEL_DIR [--json]                         tags with no concern; concerns this person has not rated
  tag SKEL_DIR TAG C<n> | tag SKEL_DIR TAG --new NAME MEANING
  rate SKEL_DIR C<n>=V ... [--date YYYY-MM-DD]
  fit SKEL_DIR [--json]                              stated against fitted weights
  predict SKEL_DIR                                   mark the round's predicted choices
  record SKEL_DIR --answers "Q1=2, Q2=Other, Q3=none" [--asked STAMP]
  hits SKEL_DIR [--json]                             hit rates of logged predictions

Standard library only.
"""
import argparse
import datetime
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass, field

LOG = ".interviews.md"
WEIGHTS = ".interview-weights.md"
DRAFT = ".interview-round.md"
LOG_TITLE = "# skel interviews"
WEIGHTS_TITLE = "# skel interview weights"
DRAFT_TITLE = "# skel interview round"
SEED = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "references", "interview-tags.md")

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
FIELD_RE = re.compile(r"^(answer|prediction|concern-only|axis|probes): (.*)$")
CONCERN_RE = re.compile(r"^## C(\d+) (\S.*)$")
RATING_RE = re.compile(r"^(\d+(?:\.\d+)?) · by: (.+) · (\d{4}-\d{2}-\d{2})$")
AXIS_RE = re.compile(r"^C(\d+) .+ vs C(\d+) .+$")
PAIR_RE = re.compile(r"^(\S+) ([123])$")
META_KEYS = ("header", "round", "select", "asked", "by")
FIELD_ORDER = ("answer", "prediction", "concern-only", "axis", "probes")
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
    skel: str
    problems: Problems
    log: list
    log_lines: list           # None when the log does not exist yet
    concerns: list
    weights_lines: list
    seeded: bool              # True when the weights come from the seed, not a file
    draft: list               # None when there is no round
    draft_lines: list

    def path(self, name):
        return os.path.join(self.skel, name)


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
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(path)), prefix=".tmp-", suffix=".md")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", errors="surrogateescape", newline="") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


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
        if log and "round" in rec.meta and not rec.meta["round"].isdigit():
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


def seed_lines():
    lines = read_lines(SEED)
    first = next(k for k, line in enumerate(lines) if CONCERN_RE.match(line.rstrip("\r\n")))
    return [WEIGHTS_TITLE + "\n", "\n"] + lines[first:]


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


def load(skel):
    if not os.path.isdir(skel):
        sys.exit(f"not a directory: {skel}")
    problems = Problems()

    def lines_of(name):
        path = os.path.join(skel, name)
        return read_lines(path) if os.path.exists(path) else None

    log_lines, weights_lines, draft_lines = lines_of(LOG), lines_of(WEIGHTS), lines_of(DRAFT)
    log = []
    if log_lines is not None:
        log = parse_records(os.path.join(skel, LOG), log_lines, LOG_TITLE, problems)
        validate_records(os.path.join(skel, LOG), log, problems, log=True)
    seeded = weights_lines is None
    if seeded:
        weights_lines = seed_lines()
    concerns = parse_weights(os.path.join(skel, WEIGHTS), weights_lines, problems)
    draft = None
    if draft_lines is not None:
        draft = parse_records(os.path.join(skel, DRAFT), draft_lines, DRAFT_TITLE, problems)
        validate_records(os.path.join(skel, DRAFT), draft, problems, log=False)
    tags = tag_map(concerns)
    for name, recs in ((LOG, log), (DRAFT, draft or [])):
        for rec in recs:
            for c in rec.choices:
                for tag in c.tags():
                    if tag not in tags:
                        problems.warn(os.path.join(skel, name), c.line + 1,
                                      f"tag `{tag}` belongs to no concern; map it with `interview.py tag`")
    return State(skel, problems, log, log_lines, concerns, weights_lines, seeded, draft, draft_lines)


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


def fail_on_errors(state):
    if state.problems.errors:
        for line in state.problems.errors:
            print(line, file=sys.stderr)
        sys.exit("fix these first (`interview.py parse SKEL_DIR` lists them)")


def person(args):
    if getattr(args, "by", None):
        return args.by
    try:
        name = subprocess.run(["git", "config", "user.name"], capture_output=True, text=True,
                              cwd=os.path.abspath(args.skel)).stdout.strip()
    except OSError:
        name = ""
    if not name:
        sys.exit("no --by given and `git config user.name` is not set; pass --by NAME")
    return name


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


def cmd_concerns(args):
    state = load(args.skel)
    fail_on_errors(state)
    by = person(args)
    unmapped, used = used_concerns(state, relevant(state, by))
    rated = stated(state.concerns, by)
    unrated = [c for c in state.concerns if c.cid in used and c.cid not in rated]
    if args.json:
        print(json.dumps({"by": by, "unmapped": sorted(unmapped),
                          "unrated": [{"id": c.cid, "name": c.name, "meaning": c.meaning} for c in unrated]}))
        return 0
    if unmapped:
        print("Tags with no concern (map each with `interview.py tag`):")
        for tag in sorted(unmapped):
            print(f"  {tag}")
    if unrated:
        print(f"Concerns {by} has not rated (rate them with `interview.py rate`):")
        for c in unrated:
            print(f"  {c.title}: {c.meaning}")
    if not unmapped and not unrated:
        print(f"Nothing to map or rate for {by}.")
    return 0


def cmd_tag(args):
    state = load(args.skel)
    fail_on_errors(state)
    tag = args.tag
    if not TAG_RE.match(tag):
        sys.exit(f"`{tag}` is not a tag: lower case, digits and hyphens, optionally after `NEW:`")
    if bool(args.concern) == bool(args.new):
        sys.exit("give a concern (`C<n>`) or `--new NAME MEANING`, not both")
    tags = tag_map(state.concerns)
    if tag in tags:
        sys.exit(f"`{tag}` already belongs to {tags[tag].title}; a tag belongs to one concern")
    lines = list(state.weights_lines)
    nl = newline_of(lines)
    if args.new:
        name, meaning = args.new
        cid = max((c.cid for c in state.concerns), default=0) + 1
        if lines and not lines[-1].endswith(("\n", "\r")):
            lines[-1] += nl
        lines += [nl, f"## C{cid} {name}{nl}", f"meaning: {meaning}{nl}", f"tags: {tag}{nl}"]
        title = f"C{cid} {name}"
    else:
        m = re.match(r"^C(\d+)$", args.concern)
        concern = next((c for c in state.concerns if m and c.cid == int(m.group(1))), None)
        if concern is None:
            sys.exit(f"no concern {args.concern} in {WEIGHTS}")
        k = concern.tags_line
        lines[k] = "tags: " + ", ".join(concern.tags + [tag]) + line_end(lines[k], nl)
        title = concern.title
    write(state.path(WEIGHTS), "".join(lines))
    print(f"`{tag}` belongs to {title}")
    return 0


def cmd_rate(args):
    state = load(args.skel)
    fail_on_errors(state)
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
    write(state.path(WEIGHTS), "".join(lines))
    for concern, value in ratings:
        print(f"{concern.title}: {fmt(value)} ({by})")
    return 0


def readiness(state, by):
    errors = []
    unmapped, used = used_concerns(state, relevant(state, by))
    errors += [f"tag `{t}` belongs to no concern: run `interview.py tag SKEL_DIR {t} C<n>` "
               f"or `--new NAME MEANING`" for t in sorted(unmapped)]
    rated = stated(state.concerns, by)
    by_id = {c.cid: c for c in state.concerns}
    errors += [f"{by_id[cid].title} is not rated by {by}: run `interview.py rate SKEL_DIR C{cid}=<0-10>`"
               for cid in sorted(used - set(rated))]
    return errors


def cmd_predict(args):
    state = load(args.skel)
    fail_on_errors(state)
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
        rec.marks = [m for m in rec.marks if m != "probe"]
        rec.fields.pop("probes", None)
        a = probe_axis(vecs, counts)
        if a:
            rec.marks.insert(0, "probe")
            rec.fields["probes"] = axis_text(a, by_id)
        print(f"Q{rec.number}: {labels} (lead {fmt(gap)})" + (f", probe: {rec.fields['probes']}" if a else ""))
    print(f"model: {model} ({n} tracers; {MIN_TRACERS} needed to fit)")
    write(state.path(DRAFT), rebuild(state.draft_lines, state.draft))
    return 0


ANSWER_RE = re.compile(r"^Q(\d+)=(.+)$")


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


def answer_errors(rec, tokens, tags):
    errors = []
    offered = [c for c in rec.choices if c.label != "Other"]
    other = rec.choice("Other")
    if "prediction" not in rec.fields:
        errors.append(f"Q{rec.number} has no prediction: run `interview.py predict` first")
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
                errors.append(f"Q{rec.number}: map the Other choice's tags with `interview.py tag` first")
        elif t.isdigit():
            if not 1 <= int(t) <= len(offered):
                errors.append(f"Q{rec.number}: choice {t} is out of range 1-{len(offered)}")
        elif t != "none":
            errors.append(f"Q{rec.number}={t}: an answer is a choice number, `Other` or `none`")
    if other is not None and "other" not in tokens:
        errors.append(f"Q{rec.number} has an Other choice, so its answer is Other")
    return errors


def cmd_record(args):
    state = load(args.skel)
    fail_on_errors(state)
    by = person(args)
    if state.draft is None:
        sys.exit(f"no round to record: {DRAFT} does not exist")
    try:
        answers = parse_answers(args.answers)
    except ValueError as e:
        sys.exit(str(e))
    asked = args.asked or datetime.datetime.now().astimezone().strftime(STAMP_FORMAT)
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
            errors += answer_errors(rec, answers[rec.number], tags)
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
    write(state.path(LOG), text)
    os.remove(state.path(DRAFT))
    hits = answered = 0
    for rec in state.draft:
        sel = {c.label for c in rec.selected()}
        answered += bool(sel)
        hits += bool(sel) and sel == {c.label for c in rec.predicted()}
        note = f", tracer: {rec.fields['axis']}" if "tracer" in rec.marks else ""
        answer = " + ".join(sorted(sel)) if sel else "declined"
        print(f"Q{rec.number}: {answer}{note}")
    print(f"round {rnd}: {hits} of {answered} predictions hit")
    return 0


def cmd_fit(args):
    state = load(args.skel)
    fail_on_errors(state)
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
    state = load(args.skel)
    fail_on_errors(state)
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
    state = load(args.skel)
    for line in state.problems.errors:
        print("error: " + line)
    for line in state.problems.warnings:
        print("warning: " + line)
    n = len(state.log)
    draft = f", round being asked: {len(state.draft)} questions" if state.draft is not None else ""
    seeded = " (from the seed; no weights file yet)" if state.seeded else ""
    print(f"{n} record{'s' if n != 1 else ''}, {len(state.concerns)} concerns{seeded}{draft}")
    return 1 if state.problems.errors else 0


COMMANDS = {"parse": cmd_parse, "concerns": cmd_concerns, "tag": cmd_tag, "rate": cmd_rate,
            "predict": cmd_predict, "record": cmd_record, "fit": cmd_fit, "hits": cmd_hits}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def command(name, by=True, json_flag=False):
        p = sub.add_parser(name)
        p.add_argument("skel")
        if by:
            p.add_argument("--by")
        if json_flag:
            p.add_argument("--json", action="store_true")
        return p

    command("parse", by=False)
    command("concerns", json_flag=True)
    p = command("tag", by=False)
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
    command("fit", json_flag=True)
    command("hits", json_flag=True)
    args = ap.parse_args(argv)
    return COMMANDS[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
