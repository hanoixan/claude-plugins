#!/usr/bin/env python3
"""wrist_lint.py: scan text for a profile's searchable clichés. Pure functions; no file access.

Two formats: `prose` (a hit is skipped inside quoted dialogue when its scope is `narration`) and `fountain`
(screenplay text: a hit counts only on lines of the kind its scope names). The Fountain rules here must stay
the same as publish/screenplay/fountain.lua; tests/fountain_cases.json is checked against both.
"""
import re

SCENE_STARTS = ("INT./EXT", "INT/EXT", "INT", "EXT", "EST", "I/E")
NOT_LINTED = ("blank", "dropped", "pagebreak", "marker")


def in_dialogue(line, pos):
    """True when position `pos` of the line lies inside a double-quoted span that opened on this line."""
    inside = False
    for ch in line[:pos]:
        if ch == '"':
            inside = not inside
        elif ch == "“":
            inside = True
        elif ch == "”":
            inside = False
    return inside


def strip_comments(text):
    """Remove boneyard /* */ and notes [[ ]], exactly as the reader does."""
    text = text.replace("\r\n", "\n")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"\[\[.*?\]\]", "", text, flags=re.S)


def mask_comments(text):
    """Blank boneyard and notes with spaces but keep every newline, so line numbers do not move."""
    def blank(m):
        return re.sub(r"[^\n]", " ", m.group(0))
    text = text.replace("\r\n", "\n")
    text = re.sub(r"/\*.*?\*/", blank, text, flags=re.S)
    return re.sub(r"\[\[.*?\]\]", blank, text, flags=re.S)


def _blank(line):
    return line is None or not line.strip()


def _upper_name(line):
    core = re.sub(r"\s*\([^()]*\)\s*$", "", line)
    return bool(re.search(r"[^\W\d_]", core)) and core == core.upper() and bool(core.strip())


def _natural_heading(line):
    up = line.upper()
    return any(up.startswith(s) and len(up) > len(s) and up[len(s)] in ". " for s in SCENE_STARTS)


def _classify(lines):
    out, i, n = [], 0, len(lines)

    def prev_blank(k):
        return k == 0 or _blank(lines[k - 1])

    def next_blank(k):
        return k + 1 >= n or _blank(lines[k + 1])

    while i < n:
        line = lines[i]
        if _blank(line):
            out.append((i + 1, "blank", line)); i += 1
        elif re.match(r"^===+\s*$", line):
            out.append((i + 1, "pagebreak", line)); i += 1
        elif re.match(r"^@@ACT .*?@@\s*$", line):
            out.append((i + 1, "marker", line)); i += 1
        elif line.startswith("#") or (line.startswith("=") and not re.match(r"^===", line)):
            out.append((i + 1, "dropped", line)); i += 1
        elif re.match(r"^\.[^.]", line) or (_natural_heading(line) and prev_blank(i) and next_blank(i)):
            out.append((i + 1, "heading", line)); i += 1
        elif re.match(r"^>\s*.*?\s*<\s*$", line):
            out.append((i + 1, "centered", line)); i += 1
        elif line.startswith(">") or (_upper_name(line) and re.search(r"TO:\s*$", line) and prev_blank(i) and next_blank(i)):
            out.append((i + 1, "transition", line)); i += 1
        elif line.startswith("!"):
            out.append((i + 1, "action", line)); i += 1
        elif prev_blank(i) and not next_blank(i) and (line.startswith("@") or (_upper_name(line) and not re.search(r"TO:\s*$", line))):
            out.append((i + 1, "character", line)); i += 1
            while i < n and not _blank(lines[i]):
                kind = "parenthetical" if re.match(r"^\s*\(.*\)\s*$", lines[i]) else "dialogue"
                out.append((i + 1, kind, lines[i])); i += 1
        else:
            while i < n and not _blank(lines[i]):
                out.append((i + 1, "action", lines[i])); i += 1
    return out


def classify_fountain(text):
    """[(line number, kind, comment-masked line)] for every line of a Fountain text."""
    return _classify(mask_comments(text).split("\n"))


def elements(text):
    """The element kinds the Fountain reader produces, in order. Consecutive dialogue lines, and consecutive
    action lines, are one element; blank and dropped lines produce none."""
    kinds, prev = [], None
    for _, kind, _ in _classify(strip_comments(text).split("\n")):
        if kind in ("blank", "dropped"):
            prev = None
            continue
        kind = {"heading": "scene-heading", "marker": "act-marker"}.get(kind, kind)
        if kind in ("dialogue", "action") and prev == kind:
            continue
        kinds.append(kind)
        prev = kind
    return kinds


def _fits(scope, kind):
    if kind in NOT_LINTED:
        return False
    if scope == "action":
        return kind == "action"
    if scope == "dialogue":
        return kind in ("dialogue", "parenthetical")
    return True


def lint_text(text, items, lint_format="prose"):
    """Hits as dicts, sorted by line then id."""
    compiled = [(item, re.compile(item["pattern"], re.IGNORECASE)) for item in items]
    hits = []
    if lint_format == "fountain":
        numbered = [(n, line) for n, kind, line in classify_fountain(text) if kind not in NOT_LINTED]
        kinds = {n: kind for n, kind, _ in classify_fountain(text)}
    else:
        numbered = list(enumerate(text.split("\n"), 1))
        kinds = {}
    for n, line in numbered:
        for item, rx in compiled:
            if lint_format == "fountain" and not _fits(item["scope"], kinds[n]):
                continue
            for m in rx.finditer(line):
                if lint_format != "fountain" and item["scope"] == "narration" and in_dialogue(line, m.start()):
                    continue
                hits.append({"line": n, "id": item["id"], "label": item["label"],
                             "text": m.group(0), "note": item["note"]})
    return sorted(hits, key=lambda h: (h["line"], h["id"]))
