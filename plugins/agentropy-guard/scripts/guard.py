#!/usr/bin/env python3
"""agentropy-guard: the architecture ledger, the person's awareness of it, erosion signals and the education queue.

State lives in .agentropy-guard/ at the git root (the working directory outside a repository; --dir overrides it).
The person's awareness lives in ~/.claude/agentropy-guard/<project-hash>/awareness.json. Run a command with --help
for its arguments.
"""
import argparse
import copy
import datetime
import fnmatch
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

STORE = ".agentropy-guard"
CONFIG = "config.json"
LEDGER = "ledger.json"
FINDINGS = "findings.json"
PENDING = "pending.json"
AWARENESS = "awareness.json"
REPORTS = "reports"
GITIGNORE_LINES = (f"{STORE}/{PENDING}", f"{STORE}/{REPORTS}/")
GUARD = f'python3 "{os.path.abspath(__file__)}"'
TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

CATEGORIES = ("boundary", "contract", "data-model", "cross-cutting", "dependency", "decision", "integration",
              "runtime-topology", "invariant")
ORIGINS = ("agent-decision", "human-decision", "discovered", "unknown")
STATUSES = ("active", "superseded", "resolved")
SEVERITIES = ("low", "medium", "high")
DECISIONS = ("accepted-risk", "will-fix", "fixed", "false-positive")
LEVELS = ("mentioned", "explained", "report_generated")
RESPONSES = ("none", "dismissed", "acknowledged", "wants_more", "snoozed")
SIGNALS = ("user_edited_file", "user_prompt_mentioned", "agent_summarized", "agent_silent_change")
FACTORS = ("blast_radius", "cross_cutting", "irreversibility", "change_frequency")
DETECTORS = ("adapter-proliferation", "duplicate-model", "point-to-point", "boundary-drift", "private-contract",
             "contract-churn", "missing-decision-record")
FINDING_SIGNALS = DETECTORS + ("orphaned-cross-cutting", "silent-decision")
EVIDENCE_TYPES = {"file": "path", "commit": "sha", "pr": "url"}
ITEM_FIELDS = ("id", "title", "category", "summary", "evidence", "components", "importance", "importance_factors",
               "origin", "created_at", "updated_at", "status")
FINDING_FIELDS = ("id", "signal", "severity", "description", "evidence", "components", "conway_mechanism",
                  "suggested_countermove", "detected_at", "user_decision", "key")

DEFAULTS = {
    "components": {},
    "allowed_edges": [],
    "contract_dirs": ["contracts", "schemas", "proto", "openapi", "api/schema"],
    "adr_dirs": ["docs/adr", "docs/decisions", "adr", "decisions"],
    "weights": {"blast_radius": 0.3, "cross_cutting": 0.25, "irreversibility": 0.25, "change_frequency": 0.2,
                "agent_boost": 0.1},
    "priors": {"agent-decision": 0.7, "discovered": 0.4, "unknown": 0.5, "human-decision": 0.2},
    "thresholds": {"importance": 0.5, "unknown": 0.5, "nudge_priority": 0.4, "silent_importance": 0.7},
    "rates": {"nudge_days": 1, "snooze_days": 7, "half_life_days": 30, "stale_commits": 50, "stale_days": 14},
    "detectors": {name: True for name in DETECTORS},
}

REGISTRY = {}


def arg(*names, **kw):
    return names, kw


def command(name, *arguments):
    """Register a subcommand; a two-word name (`item add`) becomes a nested subcommand."""
    def wrap(fn):
        REGISTRY[name] = (fn, arguments)
        return fn
    return wrap


# --- time and git ---

def parse_time(s):
    return datetime.datetime.strptime(s, TIME_FORMAT).replace(tzinfo=datetime.timezone.utc)


def now():
    fixed = os.environ.get("AGENTROPY_GUARD_NOW")
    if fixed:
        return parse_time(fixed)
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)


def iso(dt):
    return dt.astimezone(datetime.timezone.utc).strftime(TIME_FORMAT)


def today():
    return now().date().isoformat()


def time_ok(s):
    try:
        parse_time(s)
        return True
    except (TypeError, ValueError):
        return False


def git(root, *args):
    """git's stdout, or None when git is missing or the command fails."""
    try:
        out = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout if out.returncode == 0 else None


def git_root(cwd):
    out = git(cwd, "rev-parse", "--show-toplevel")
    return out.strip() if out and out.strip() else os.path.abspath(cwd)


# --- the store ---

class Store:
    def __init__(self, directory):
        self.dir = os.path.abspath(directory)
        self.root = os.path.dirname(self.dir)

    def path(self, name):
        return os.path.join(self.dir, name)

    @property
    def exists(self):
        return os.path.isdir(self.dir)

    def aware_path(self):
        home = os.environ.get("AGENTROPY_GUARD_HOME") or os.path.join(os.path.expanduser("~"), ".claude",
                                                                      "agentropy-guard")
        digest = hashlib.sha256(os.path.realpath(self.root).encode("utf-8")).hexdigest()[:12]
        return os.path.join(home, digest, AWARENESS)


def store_for(cwd):
    return Store(os.path.join(git_root(cwd), STORE))


def store_of(args):
    return Store(args.dir) if getattr(args, "dir", None) else store_for(os.getcwd())


def read_json(path, default):
    if not os.path.exists(path):
        return copy.deepcopy(default)
    with open(path, encoding="utf-8") as fh:
        try:
            return json.load(fh)
        except ValueError as e:
            raise ValueError(f"{path} is not valid JSON: {e}") from None


def write_json(path, data):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".", prefix=".tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, sort_keys=True, ensure_ascii=False)
            fh.write("\n")
        mask = os.umask(0)
        os.umask(mask)
        os.chmod(tmp, 0o666 & ~mask)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def empty_ledger():
    return {"items": [], "last_scan": None}


def empty_findings():
    return {"findings": []}


def empty_awareness():
    return {"items": {}, "state": {}}


def empty_pending():
    return {"session": None, "edits": [], "turn_mark": 0, "candidates": []}


def merged_config(raw):
    cfg = {}
    for key, value in DEFAULTS.items():
        given = raw.get(key, value) if isinstance(raw, dict) else value
        cfg[key] = {**value, **given} if isinstance(value, dict) and isinstance(given, dict) else given
    return copy.deepcopy(cfg)


def config(store):
    return merged_config(read_json(store.path(CONFIG), {}))


# --- validation ---

def number(x, lo=0.0, hi=1.0):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and lo <= x <= hi


def strings(x):
    return isinstance(x, list) and all(isinstance(s, str) and s for s in x)


def config_errors(raw):
    if not isinstance(raw, dict):
        return ["the file is not a JSON object"]
    e = [f"unknown key `{key}`" for key in sorted(set(raw) - set(DEFAULTS))]
    comps = raw.get("components", {})
    if not isinstance(comps, dict) or not all(strings(v) for v in comps.values()):
        e.append("`components` maps a component name to a list of path globs")
    edges = raw.get("allowed_edges", [])
    if not isinstance(edges, list) or not all(strings(x) and len(x) == 2 for x in edges):
        e.append("`allowed_edges` is a list of [from, to] component pairs")
    for key in ("contract_dirs", "adr_dirs"):
        if not strings(raw.get(key, [])):
            e.append(f"`{key}` is a list of folders")
    for key in ("weights", "priors", "thresholds", "rates", "detectors"):
        value = raw.get(key, {})
        if not isinstance(value, dict):
            e.append(f"`{key}` is an object")
            continue
        for k, x in value.items():
            if k not in DEFAULTS[key]:
                e.append(f"unknown `{key}.{k}`")
            elif key == "detectors" and not isinstance(x, bool):
                e.append(f"`detectors.{k}` is true or false")
            elif key == "rates" and not number(x, 0.001, 1e6):
                e.append(f"`rates.{k}` is a positive number")
            elif key not in ("detectors", "rates") and not number(x):
                e.append(f"`{key}.{k}` is a number from 0 to 1")
    return e


def evidence_errors(ev):
    if not isinstance(ev, list) or not ev:
        return ["`evidence` is a non-empty list"]
    e = []
    for x in ev:
        if not isinstance(x, dict) or x.get("type") not in EVIDENCE_TYPES:
            e.append(f"evidence `type` is one of {', '.join(EVIDENCE_TYPES)}")
            continue
        need = EVIDENCE_TYPES[x["type"]]
        if not isinstance(x.get(need), str) or not x[need]:
            e.append(f"{x['type']} evidence needs `{need}`")
    return e


def item_errors(it):
    if not isinstance(it, dict):
        return ["an item is a JSON object"]
    missing = [k for k in ITEM_FIELDS if k not in it]
    if missing:
        return [f"missing {', '.join(missing)}"]
    e = []
    if not isinstance(it["id"], str) or not re.fullmatch(r"ki_\d{4,}", it["id"]):
        e.append("`id` is ki_NNNN")
    for k in ("title", "summary"):
        if not isinstance(it[k], str) or not it[k].strip():
            e.append(f"`{k}` is a non-empty string")
    if not isinstance(it.get("details", ""), str):
        e.append("`details` is a string")
    for k, allowed in (("category", CATEGORIES), ("origin", ORIGINS), ("status", STATUSES)):
        if it[k] not in allowed:
            e.append(f"`{k}` is one of {', '.join(allowed)}")
    if it["status"] == "superseded" and not it.get("superseded_by"):
        e.append("a superseded item names `superseded_by`")
    e += evidence_errors(it["evidence"])
    if not isinstance(it["components"], list) or not all(isinstance(c, str) and c for c in it["components"]):
        e.append("`components` is a list of component names")
    f = it["importance_factors"]
    if not isinstance(f, dict) or set(f) - set(FACTORS) or not all(number(x) for x in f.values()):
        e.append(f"`importance_factors` holds {', '.join(FACTORS)}, each from 0 to 1")
    if not number(it["importance"]):
        e.append("`importance` is from 0 to 1")
    for k in ("created_at", "updated_at"):
        if not time_ok(it[k]):
            e.append(f"`{k}` is YYYY-MM-DDTHH:MM:SSZ")
    if not strings(it.get("related_findings", [])) and it.get("related_findings") != []:
        e.append("`related_findings` is a list of finding ids")
    return e


def finding_errors(f):
    if not isinstance(f, dict):
        return ["a finding is a JSON object"]
    missing = [k for k in FINDING_FIELDS if k not in f]
    if missing:
        return [f"missing {', '.join(missing)}"]
    e = []
    if not isinstance(f["id"], str) or not re.fullmatch(r"ef_\d{4,}", f["id"]):
        e.append("`id` is ef_NNNN")
    if f["signal"] not in FINDING_SIGNALS:
        e.append(f"`signal` is one of {', '.join(FINDING_SIGNALS)}")
    if f["severity"] not in SEVERITIES:
        e.append(f"`severity` is one of {', '.join(SEVERITIES)}")
    for k in ("description", "suggested_countermove", "key"):
        if not isinstance(f[k], str) or not f[k].strip():
            e.append(f"`{k}` is a non-empty string")
    e += evidence_errors(f["evidence"])
    if not isinstance(f["components"], list) or not all(isinstance(c, str) and c for c in f["components"]):
        e.append("`components` is a list of component names")
    m = f["conway_mechanism"]
    if not isinstance(m, int) or isinstance(m, bool) or not 1 <= m <= 7:
        e.append("`conway_mechanism` is a whole number from 1 to 7")
    if not time_ok(f["detected_at"]):
        e.append("`detected_at` is YYYY-MM-DDTHH:MM:SSZ")
    if f["user_decision"] is not None and f["user_decision"] not in DECISIONS:
        e.append(f"`user_decision` is null or one of {', '.join(DECISIONS)}")
    if not isinstance(f.get("cost", ""), str):
        e.append("`cost` is a string")
    return e


def awareness_errors(a):
    if not isinstance(a, dict) or not isinstance(a.get("items"), dict) or not isinstance(a.get("state"), dict):
        return ["holds `items` and `state` objects"]
    e = []
    for item_id, rec in a["items"].items():
        if not isinstance(rec, dict):
            e.append(f"{item_id}: a record is an object")
            continue
        for s in rec.get("exposure_signals", []):
            if not isinstance(s, dict) or s.get("type") not in SIGNALS or not time_ok(s.get("at")):
                e.append(f"{item_id}: an exposure signal has a known `type` and an `at` time")
        for d in rec.get("disclosures", []):
            if not isinstance(d, dict) or d.get("level") not in LEVELS or not time_ok(d.get("at")):
                e.append(f"{item_id}: a disclosure has a known `level` and an `at` time")
        if rec.get("user_response", "none") not in RESPONSES:
            e.append(f"{item_id}: `user_response` is one of {', '.join(RESPONSES)}")
    return e


def store_errors(store):
    out = []

    def load(name, default, path=None):
        try:
            return read_json(path or store.path(name), default)
        except (OSError, ValueError) as err:
            out.append(str(err))
            return copy.deepcopy(default)

    out += [f"{CONFIG}: {e}" for e in config_errors(load(CONFIG, {}))]
    ledger = load(LEDGER, empty_ledger())
    if not isinstance(ledger, dict) or not isinstance(ledger.get("items"), list):
        out.append(f"{LEDGER}: holds an `items` list and `last_scan`")
        ledger = empty_ledger()
    findings = load(FINDINGS, empty_findings())
    if not isinstance(findings, dict) or not isinstance(findings.get("findings"), list):
        out.append(f"{FINDINGS}: holds a `findings` list")
        findings = empty_findings()
    ids, fids = set(), set()
    for f in findings["findings"]:
        name = f.get("id", "?") if isinstance(f, dict) else "?"
        out += [f"{FINDINGS}: {name}: {e}" for e in finding_errors(f)]
        if name in fids:
            out.append(f"{FINDINGS}: {name} appears twice")
        fids.add(name)
    for it in ledger["items"]:
        name = it.get("id", "?") if isinstance(it, dict) else "?"
        out += [f"{LEDGER}: {name}: {e}" for e in item_errors(it)]
        if name in ids:
            out.append(f"{LEDGER}: {name} appears twice")
        ids.add(name)
    for it in (x for x in ledger["items"] if isinstance(x, dict)):
        if it.get("superseded_by") and it["superseded_by"] not in ids:
            out.append(f"{LEDGER}: {it.get('id')}: superseded by {it['superseded_by']}, which is not in the ledger")
        for fid in it.get("related_findings") or []:
            if fid not in fids:
                out.append(f"{LEDGER}: {it.get('id')}: related finding {fid} is not in {FINDINGS}")
    last = ledger.get("last_scan")
    if last is not None and (not isinstance(last, dict) or not time_ok(last.get("at"))):
        out.append(f"{LEDGER}: `last_scan` is null or {{at, commit}}")
    out += [f"awareness: {e}" for e in awareness_errors(load(AWARENESS, empty_awareness(), store.aware_path()))]
    return out


# --- commands ---

@command("init")
def cmd_init(args):
    store = store_of(args)
    os.makedirs(store.dir, exist_ok=True)
    made = []
    for name, data in ((CONFIG, copy.deepcopy(DEFAULTS)), (LEDGER, empty_ledger()), (FINDINGS, empty_findings())):
        if not os.path.exists(store.path(name)):
            write_json(store.path(name), data)
            made.append(name)
    ignore = os.path.join(store.root, ".gitignore")
    text = ""
    if os.path.exists(ignore):
        with open(ignore, encoding="utf-8") as fh:
            text = fh.read()
    add = [line for line in GITIGNORE_LINES if line not in text.splitlines()]
    if add:
        with open(ignore, "a", encoding="utf-8") as fh:
            fh.write(("\n" if text and not text.endswith("\n") else "") + "".join(f"{line}\n" for line in add))
    print(f"created: {', '.join(made)}" if made else "already set up")
    if add:
        print(f"ignored: {', '.join(add)}")
    return 0


@command("parse")
def cmd_parse(args):
    store = store_of(args)
    errors = store_errors(store)
    for e in errors:
        print(f"error: {e}")
    if not errors:
        ledger = read_json(store.path(LEDGER), empty_ledger())
        findings = read_json(store.path(FINDINGS), empty_findings())
        print(f"{len(ledger['items'])} items, {len(findings['findings'])} findings")
    return 1 if errors else 0


# --- ledger items ---

MATERIAL = ("title", "category", "summary", "details", "evidence", "components", "origin")


def load_ledger(store):
    return read_json(store.path(LEDGER), empty_ledger())


def save_ledger(store, ledger):
    ledger["items"].sort(key=lambda x: x["id"])
    write_json(store.path(LEDGER), ledger)


def next_id(prefix, ids):
    n = max((int(i.split("_")[1]) for i in ids if re.fullmatch(prefix + r"_\d+", str(i))), default=0)
    return f"{prefix}_{n + 1:04d}"


def evidence_paths(item):
    return [e["path"] for e in item.get("evidence", []) if isinstance(e, dict) and e.get("type") == "file"
            and e.get("path")]


def change_frequency(store, paths):
    """Commits touching the paths in the last 90 days, over 20, capped at 1."""
    if not paths:
        return 0.0
    out = git(store.root, "log", "--since=90.days", "--format=%H", "--", *paths)
    return min(1.0, len(set(out.split())) / 20) if out else 0.0


def importance(item, cfg):
    w, f = cfg["weights"], item["importance_factors"]
    value = sum(w[k] * f.get(k, 0.0) for k in FACTORS)
    if item["origin"] == "agent-decision":
        value += w["agent_boost"]
    return round(min(1.0, value), 4)


def read_input(source):
    if source == "-":
        text = sys.stdin.read()
    else:
        with open(source, encoding="utf-8") as fh:
            text = fh.read()
    try:
        data = json.loads(text)
    except ValueError as e:
        sys.exit(f"the input is not valid JSON: {e}")
    return data if isinstance(data, list) else [data]


def upsert_item(store, cfg, ledger, data, at):
    """The stored form of an input item: an update when `id` names an item, else a new one. Raises ValueError."""
    if not isinstance(data, dict):
        raise ValueError("an item is a JSON object")
    by_id = {it["id"]: it for it in ledger["items"]}
    stamp = iso(at)
    given = {k: v for k, v in data.items() if k not in ("created_at", "updated_at", "importance")}
    if data.get("id") is not None:
        if data["id"] not in by_id:
            raise ValueError(f"no item {data['id']}")
        old = by_id[data["id"]]
        new = {**old, **given}
        if any(new.get(k) != old.get(k) for k in MATERIAL):
            new["updated_at"] = stamp
    else:
        new = {"details": "", "status": "active", "superseded_by": None, "related_findings": [], **given,
               "id": next_id("ki", by_id), "created_at": stamp, "updated_at": stamp}
    factors = dict(new.get("importance_factors") or {})
    factors["change_frequency"] = change_frequency(store, evidence_paths(new))
    new["importance_factors"] = factors
    errors = item_errors({**new, "importance": 0.0})
    if errors:
        raise ValueError(f"{new.get('id')}: " + "; ".join(errors))
    new["importance"] = importance(new, cfg)
    return new


def find_item(ledger, item_id):
    it = next((x for x in ledger["items"] if x["id"] == item_id), None)
    if it is None:
        sys.exit(f"no item {item_id}")
    return it


@command("item add", arg("--json", dest="source", default="-",
                         help="a file holding an item or a list of items, or - for stdin"))
def cmd_item_add(args):
    store = store_of(args)
    cfg, ledger, at = config(store), load_ledger(store), now()
    saved, errors = [], []
    for data in read_input(args.source):
        try:
            it = upsert_item(store, cfg, ledger, data, at)
        except ValueError as e:
            errors.append(str(e))
            continue
        ledger["items"] = [x for x in ledger["items"] if x["id"] != it["id"]] + [it]
        saved.append(it)
    if errors:
        sys.exit("\n".join(errors))
    save_ledger(store, ledger)
    for it in saved:
        print(f"{it['id']} {it['importance']:.2f} {it['title']}")
    return 0


@command("item get", arg("id"))
def cmd_item_get(args):
    print(json.dumps(find_item(load_ledger(store_of(args)), args.id), indent=2, sort_keys=True))
    return 0


@command("item list", arg("--status", choices=STATUSES), arg("--json", action="store_true"))
def cmd_item_list(args):
    items = [it for it in load_ledger(store_of(args))["items"] if not args.status or it["status"] == args.status]
    if args.json:
        print(json.dumps(items, indent=2, sort_keys=True))
    for it in [] if args.json else items:
        print(f"{it['id']} {it['importance']:.2f} {it['category']} {it['title']}")
    return 0


@command("item supersede", arg("id"), arg("--by", required=True))
def cmd_item_supersede(args):
    store = store_of(args)
    ledger = load_ledger(store)
    old, new = find_item(ledger, args.id), find_item(ledger, args.by)
    if old is new:
        sys.exit("an item cannot supersede itself")
    old.update(status="superseded", superseded_by=new["id"], updated_at=iso(now()))
    save_ledger(store, ledger)
    print(f"{old['id']} superseded by {new['id']}")
    return 0


@command("item refresh")
def cmd_item_refresh(args):
    store = store_of(args)
    cfg, ledger = config(store), load_ledger(store)
    n = 0
    for it in (x for x in ledger["items"] if x["status"] == "active"):
        it["importance_factors"]["change_frequency"] = change_frequency(store, evidence_paths(it))
        it["importance"] = importance(it, cfg)
        n += 1
    save_ledger(store, ledger)
    print(f"{n} items refreshed")
    return 0


@command("scanned")
def cmd_scanned(args):
    store = store_of(args)
    ledger = load_ledger(store)
    head = git(store.root, "rev-parse", "HEAD")
    ledger["last_scan"] = {"at": iso(now()), "commit": head.strip() if head else None}
    save_ledger(store, ledger)
    print(f"last scan: {ledger['last_scan']['at']}")
    return 0


# --- awareness ---

MAX_SIGNALS = 50


def load_awareness(store):
    a = read_json(store.aware_path(), empty_awareness())
    a.setdefault("items", {})
    a.setdefault("state", {})
    return a


def save_awareness(store, a):
    write_json(store.aware_path(), a)


def record_of(a, item_id):
    return a["items"].setdefault(item_id, {"exposure_signals": [], "disclosures": [], "user_response": "none",
                                           "snoozed_until": None, "item_version_at_last_disclosure": None,
                                           "acknowledged_version": None})


def add_signal(a, item_id, signal):
    rec = record_of(a, item_id)
    rec["exposure_signals"] = (rec["exposure_signals"] + [signal])[-MAX_SIGNALS:]


def unknown_likelihood(item, rec, cfg, at):
    """How likely the person does not know the item, from its origin and their exposure to it."""
    prior = cfg["priors"][item["origin"]]
    rec = rec or {}
    if rec.get("user_response") == "acknowledged" and rec.get("acknowledged_version") == item["updated_at"]:
        return 0.05
    u = prior
    signals = sorted(rec.get("exposure_signals", []), key=lambda s: s["at"])
    for s in signals:
        if s["type"] == "user_edited_file":
            u *= 0.4
        elif s["type"] == "user_prompt_mentioned":
            u *= 0.7
        elif s["type"] == "agent_summarized":
            u *= 0.9
        elif s["type"] == "agent_silent_change":
            u = min(0.95, u + 0.15)
    if signals:
        days = max(0.0, (at - parse_time(signals[-1]["at"])).total_seconds() / 86400)
        u = prior + (u - prior) * 0.5 ** (days / cfg["rates"]["half_life_days"])
    return round(max(0.0, min(1.0, u)), 4)


def items_touching(ledger, path=None, component=None, item_id=None):
    """Active items an exposure applies to: by id, by a component they name, or by a file in their evidence."""
    out = []
    for it in ledger["items"]:
        if it["status"] != "active":
            continue
        if item_id is not None and it["id"] == item_id:
            out.append(it)
        elif component is not None and component in it["components"]:
            out.append(it)
        elif path is not None and any(path == p or path.startswith(p.rstrip("/") + "/") for p in evidence_paths(it)):
            out.append(it)
    return out


@command("seen", arg("--item"), arg("--path"), arg("--component"), arg("--signal", required=True, choices=SIGNALS),
         arg("--term"))
def cmd_seen(args):
    targets = [x for x in (args.item, args.path, args.component) if x]
    if len(targets) != 1:
        sys.exit("give exactly one of --item, --path or --component")
    store = store_of(args)
    ledger, a, stamp = load_ledger(store), load_awareness(store), iso(now())
    if args.item:
        find_item(ledger, args.item)
    hits = items_touching(ledger, path=args.path, component=args.component, item_id=args.item)
    for it in hits:
        signal = {"type": args.signal, "at": stamp}
        for key in ("path", "component", "term"):
            if getattr(args, key):
                signal[key] = getattr(args, key)
        add_signal(a, it["id"], signal)
    save_awareness(store, a)
    print(f"{args.signal}: {len(hits)} item{'s' if len(hits) != 1 else ''}")
    return 0


@command("told", arg("id"), arg("--level", required=True, choices=LEVELS), arg("--report"), arg("--session"))
def cmd_told(args):
    store = store_of(args)
    it = find_item(load_ledger(store), args.id)
    a = load_awareness(store)
    rec = record_of(a, it["id"])
    entry = {"level": args.level, "at": iso(now())}
    for key in ("report", "session"):
        if getattr(args, key):
            entry[key] = getattr(args, key)
    rec["disclosures"].append(entry)
    rec["item_version_at_last_disclosure"] = it["updated_at"]
    save_awareness(store, a)
    print(f"{it['id']}: {args.level}")
    return 0


@command("respond", arg("id"), arg("--response", required=True, choices=RESPONSES[1:]), arg("--days", type=float))
def cmd_respond(args):
    store = store_of(args)
    cfg, it = config(store), find_item(load_ledger(store), args.id)
    a, at = load_awareness(store), now()
    rec, state = record_of(a, it["id"]), a["state"]
    rec["user_response"] = args.response
    if args.response == "acknowledged":
        rec["acknowledged_version"] = it["updated_at"]
    if args.response == "snoozed":
        days = args.days if args.days is not None else cfg["rates"]["snooze_days"]
        rec["snoozed_until"] = iso(at + datetime.timedelta(days=days))
    state["dismissals"] = state.get("dismissals", 0) + 1 if args.response == "dismissed" else 0
    if (state.get("pending_nudge") or {}).get("item") == it["id"]:
        state["pending_nudge"] = None
    save_awareness(store, a)
    print(f"{it['id']}: {args.response}")
    return 0


# --- components and the queue ---

CONTAINERS = ("src", "packages", "services", "apps", "lib", "libs", "modules", "crates")
NOT_COMPONENTS = ("docs", "doc", "test", "tests", "node_modules", "vendor", "dist", "build", "target", "out")


def norm(path):
    p = str(path).replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    return p


def component_of(path, cfg):
    """The component a repository path belongs to: the config's mapping, else its top folder (or the one under a
    container folder such as src/), else None."""
    p = norm(path)
    for name, globs in cfg["components"].items():
        if any(fnmatch.fnmatchcase(p, glob) for glob in globs):
            return name
    if cfg["components"]:
        return None
    parts = p.split("/")
    if len(parts) < 2 or parts[0].startswith(".") or parts[0] in NOT_COMPONENTS:
        return None
    if parts[0] in CONTAINERS:
        return parts[1] if len(parts) > 2 else None
    return parts[0]


def queue(cfg, ledger, a, at, files=(), components=()):
    """Active items worth raising, most worth raising first: important, probably unknown, not yet told (or changed
    since), not snoozed; relevance 1.5 when they touch the given files or components."""
    files = {norm(f) for f in files}
    comps = set(components) | {c for c in (component_of(f, cfg) for f in files) if c}
    th, rows = cfg["thresholds"], []
    for it in ledger["items"]:
        if it["status"] != "active":
            continue
        rec = a["items"].get(it["id"]) or {}
        if rec.get("snoozed_until") and parse_time(rec["snoozed_until"]) > at:
            continue
        told = rec.get("item_version_at_last_disclosure")
        if rec.get("disclosures") and told and parse_time(it["updated_at"]) <= parse_time(told):
            continue
        unknown = unknown_likelihood(it, rec, cfg, at)
        if it["importance"] < th["importance"] or unknown < th["unknown"]:
            continue
        touched = bool(files & set(evidence_paths(it))) or bool(comps & set(it["components"]))
        relevance = 1.5 if touched else 1.0
        rows.append({"id": it["id"], "title": it["title"], "importance": it["importance"], "unknown": unknown,
                     "relevance": relevance, "priority": round(it["importance"] * unknown * relevance, 4),
                     "components": it["components"]})
    rows.sort(key=lambda r: (-r["priority"], -r["importance"], r["id"]))
    return rows


@command("queue", arg("--limit", type=int, default=5), arg("--files", nargs="*", default=[]),
         arg("--components", nargs="*", default=[]), arg("--json", action="store_true"))
def cmd_queue(args):
    store = store_of(args)
    rows = queue(config(store), load_ledger(store), load_awareness(store), now(), args.files,
                 args.components)[:args.limit]
    if args.json:
        print(json.dumps(rows, indent=2, sort_keys=True))
        return 0
    for r in rows:
        print(f"{r['id']} priority {r['priority']:.2f} (importance {r['importance']:.2f} x unknown "
              f"{r['unknown']:.2f} x relevance {r['relevance']:g}) {r['title']}")
    if not rows:
        print("nothing to raise")
    return 0


# --- main ---

def build_parser():
    ap = argparse.ArgumentParser(prog="guard.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    top = ap.add_subparsers(dest="cmd", required=True)
    groups = {}
    for name, (fn, arguments) in REGISTRY.items():
        parts = name.split()
        if len(parts) == 1:
            p = top.add_parser(parts[0])
        else:
            if parts[0] not in groups:
                groups[parts[0]] = top.add_parser(parts[0]).add_subparsers(dest="sub", required=True)
            p = groups[parts[0]].add_parser(parts[1])
        p.add_argument("--dir", help="the store (default: .agentropy-guard/ at the git root)")
        for names, kw in arguments:
            p.add_argument(*names, **kw)
        p.set_defaults(fn=fn)
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.fn(args)
    except ValueError as e:
        sys.exit(f"error: {e}")


if __name__ == "__main__":
    sys.exit(main())
