#!/usr/bin/env python3
"""estimate.py: do-next's time estimates, from the history in DONE.md.

    estimate.py ratio DONE_MD MINUTES [--last 30] [--min-tasks 3] [--json]
        Read the last LAST finished tasks in DONE_MD, keep those with a positive `estimate: N min` and
        `actual: N min`, drop outliers (Tukey fences on log(actual / estimate), with 4 or more ratios),
        and multiply MINUTES by the mean of the remaining ratios. Prints the raw and the adjusted estimate.
        With fewer than MIN_TASKS usable tasks it prints the raw estimate only.

    estimate.py elapsed START END [PAUSE_START PAUSE_END ...]
        Working minutes from START to END, less each pause, rounded, at least 1. Times are
        `YYYY-MM-DD HH:MM:SS +ZZZZ`, as printed by `date '+%Y-%m-%d %H:%M:%S %z'`.

The adjusted estimate is for telling the user. It is never written to the run file or DONE.md.
Standard library only.
"""
import argparse
import datetime
import json
import math
import re
import statistics
import sys

STAMP_RE = re.compile(r"^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} [+-]\d{4}\]$")
FIELD_RE = re.compile(r"^(estimate|actual):\s*(\d+)\s*min\s*$")
TIME_FORMAT = "%Y-%m-%d %H:%M:%S %z"


def tasks(text):
    """The DONE.md entries that are finished tasks, oldest first: each a list of the lines that follow its
    `[timestamp]` line, up to the entry's `--` separator."""
    out, current = [], None
    for raw in text.replace("\r\n", "\n").split("\n"):
        line = raw.strip()
        if line == "--":
            if current is not None:
                out.append(current)
            current = None
        elif STAMP_RE.match(line):
            current = []
        elif current is not None:
            current.append(line)
    if current is not None:
        out.append(current)
    return out


def header_fields(lines):
    """`estimate` and `actual` from the lines directly after the timestamp, before the prompt text."""
    fields = {}
    for line in lines:
        m = FIELD_RE.match(line)
        if not m:
            break
        fields[m.group(1)] = int(m.group(2))
    return fields


def history(text, last=30):
    """(estimate, actual) for each of the last LAST finished tasks that records both, oldest first."""
    pairs = []
    for lines in tasks(text)[-last:]:
        f = header_fields(lines)
        if f.get("estimate", 0) > 0 and f.get("actual", 0) > 0:
            pairs.append((f["estimate"], f["actual"]))
    return pairs


def adjust(pairs, minutes, min_tasks=3):
    """The adjusted estimate for MINUTES from (estimate, actual) pairs: a dict with ratio, adjusted (None
    with too little history), used and discarded."""
    ratios = [actual / est for est, actual in pairs]
    result = {"estimate": minutes, "ratio": None, "adjusted": None, "used": len(ratios), "discarded": 0,
              "min_tasks": min_tasks}
    if len(ratios) < min_tasks:
        return result
    kept = ratios
    if len(ratios) >= 4:
        logs = [math.log(r) for r in ratios]
        q1, _, q3 = statistics.quantiles(logs, n=4, method="inclusive")
        low, high = q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
        kept = [r for r, lg in zip(ratios, logs) if low <= lg <= high]
    ratio = statistics.fmean(kept)
    result.update(ratio=ratio, adjusted=max(1, round(minutes * ratio)), used=len(kept),
                  discarded=len(ratios) - len(kept))
    return result


def parse_time(value):
    return datetime.datetime.strptime(value.strip(), TIME_FORMAT)


def elapsed(start, end, pauses):
    """Working minutes from START to END less each (pause start, pause end), rounded, at least 1."""
    total = (parse_time(end) - parse_time(start)).total_seconds()
    for p_start, p_end in pauses:
        length = (parse_time(p_end) - parse_time(p_start)).total_seconds()
        if length < 0:
            raise ValueError(f"the pause from {p_start} to {p_end} ends before it starts")
        total -= length
    return max(1, round(total / 60))


def describe(r):
    if r["adjusted"] is None:
        return (f"Estimate: {r['estimate']} min. Not enough history to adjust yet "
                f"({r['used']} of {r['min_tasks']} tasks needed).")
    return (f"Estimate: {r['estimate']} min. Adjusted from history: {r['adjusted']} min "
            f"(ratio {r['ratio']:.2f} from {r['used']} tasks, {r['discarded']} outliers discarded).")


def positive_int(value):
    if not re.fullmatch(r"\d+", value) or int(value) < 1:
        raise argparse.ArgumentTypeError(f"must be a whole number of minutes, at least 1 (got '{value}')")
    return int(value)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("ratio")
    r.add_argument("done_md")
    r.add_argument("minutes", type=positive_int)
    r.add_argument("--last", type=positive_int, default=30)
    r.add_argument("--min-tasks", type=positive_int, default=3)
    r.add_argument("--json", action="store_true")
    e = sub.add_parser("elapsed")
    e.add_argument("start")
    e.add_argument("end")
    e.add_argument("pauses", nargs="*")
    args = ap.parse_args(argv)
    if args.cmd == "ratio":
        try:
            with open(args.done_md, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except FileNotFoundError:
            text = ""
        result = adjust(history(text, args.last), args.minutes, args.min_tasks)
        print(json.dumps(result) if args.json else describe(result))
        return 0
    if len(args.pauses) % 2:
        ap.error("pauses come in start and end pairs")
    try:
        pauses = list(zip(args.pauses[0::2], args.pauses[1::2]))
        print(elapsed(args.start, args.end, pauses))
    except ValueError as exc:
        ap.error(str(exc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
