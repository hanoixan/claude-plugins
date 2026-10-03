#!/usr/bin/env python3
"""wrist_lint.py: scan prose for a profile's searchable clichés. Pure functions; no file access."""
import re


def in_dialogue(line, pos):
    """True when position `pos` of the line lies inside a double-quoted span that opened on this line."""
    inside = False
    for ch in line[:pos]:
        if ch == '"':
            inside = not inside
        elif ch == "\u201c":
            inside = True
        elif ch == "\u201d":
            inside = False
    return inside


def lint_text(text, items):
    """Hits as dicts, sorted by line then id. A `narration` item is not reported inside dialogue."""
    compiled = [(item, re.compile(item["pattern"], re.IGNORECASE)) for item in items]
    hits = []
    for n, line in enumerate(text.split("\n"), 1):
        for item, rx in compiled:
            for m in rx.finditer(line):
                if item["scope"] == "narration" and in_dialogue(line, m.start()):
                    continue
                hits.append({"line": n, "id": item["id"], "label": item["label"],
                             "text": m.group(0), "note": item["note"]})
    return sorted(hits, key=lambda h: (h["line"], h["id"]))
