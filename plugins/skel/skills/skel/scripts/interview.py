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


COMMANDS = {"parse": cmd_parse, "concerns": cmd_concerns, "tag": cmd_tag, "rate": cmd_rate}


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
    args = ap.parse_args(argv)
    return COMMANDS[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
