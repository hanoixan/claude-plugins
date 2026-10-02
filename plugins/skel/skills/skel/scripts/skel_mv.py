#!/usr/bin/env python3
"""skel_mv.py: move or rename Skel stand-ins (files or directories) and rewrite every
relative markdown link in the skel tree so cross-references stay valid.

  skel_mv.py SKEL_DIR OLD NEW [--dry-run]
  skel_mv.py SKEL_DIR --map mapping.txt [--dry-run]

mapping.txt has one "OLD NEW" pair per line (paths relative to the current directory;
'#' starts a comment). Use it when adapting an abstract system, e.g.:

  skel/undo/history.code.skel.md    skel/src/editor/undo/history.ts.skel.md
  skel/infra/history_store.iac.skel.md  skel/infra/undo_store.tf.skel.md

A `unit:` path in front matter is rewritten the same way. Links inside fenced code blocks
are left untouched.
"""
import argparse
import os
import re
import shutil
import sys

LINK_RE = re.compile(r"(\[[^\]]*\]\()(\s*)([^)\s#]*)(#[^)\s]*)?((?:\s+\"[^\"]*\")?\s*\))")
FENCE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
EXTERNAL_RE = re.compile(r"^[a-z][a-z0-9+.-]*:", re.I)
UNIT_RE = re.compile(r"^(\s*unit\s*:\s*)(\S+)(\s*)$", re.I)
META_RE = re.compile(r"^\s*[A-Za-z_]+\s*:")


def expand(pairs):
    mapping = {}
    for old, new in pairs:
        old, new = os.path.abspath(old), os.path.abspath(new)
        if os.path.isdir(old):
            for dp, _, fns in os.walk(old):
                for fn in fns:
                    src = os.path.join(dp, fn)
                    mapping[src] = os.path.join(new, os.path.relpath(src, old))
        elif os.path.isfile(old):
            if os.path.isdir(new):
                new = os.path.join(new, os.path.basename(old))
            mapping[old] = new
        else:
            sys.exit(f"no such file or directory: {old}")
    for src, dst in mapping.items():
        if os.path.exists(dst) and dst not in mapping:
            sys.exit(f"destination exists: {dst}")
    return mapping


def rewrite(text, old_loc, new_loc, mapping):
    out, fence, changed = [], None, 0
    lines = text.split("\n")
    front_end = 0       # front matter is closed by `---` after nothing but `key: value` and blank lines
    if lines and lines[0].strip() == "---":
        for j in range(1, len(lines)):
            if lines[j].strip() == "---":
                front_end = j
                break
            if lines[j].strip() and not META_RE.match(lines[j]):
                break

    def moved(path):
        """The relative path to write instead, or None when this one still holds."""
        if not path or EXTERNAL_RE.match(path):
            return None
        old_target = os.path.normpath(os.path.join(os.path.dirname(old_loc), path))
        target = mapping.get(old_target, old_target)
        if target == old_target and new_loc == old_loc:
            return None
        rel = os.path.relpath(target, os.path.dirname(new_loc))
        if not rel.startswith("."):
            rel = "./" + rel
        return None if rel == path else rel

    def sub(m):
        nonlocal changed
        rel = moved(m.group(3))
        if rel is None:
            return m.group(0)
        changed += 1
        return f"{m.group(1)}{m.group(2)}{rel}{m.group(4) or ''}{m.group(5)}"

    for idx, line in enumerate(lines):
        if 0 < idx < front_end:
            um = UNIT_RE.match(line)
            rel = moved(um.group(2)) if um else None
            if rel is not None:
                changed += 1
                line = f"{um.group(1)}{rel}{um.group(3)}"
            out.append(LINK_RE.sub(sub, line))
            continue
        fm = FENCE_RE.match(line)
        if fence:
            if fm and fm.group(1)[0] == fence[0] and len(fm.group(1)) >= len(fence):
                fence = None
            out.append(line)
            continue
        if fm:
            fence = fm.group(1)
            out.append(line)
            continue
        out.append(LINK_RE.sub(sub, line))
    return "\n".join(out), changed


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("skel_dir")
    ap.add_argument("old", nargs="?")
    ap.add_argument("new", nargs="?")
    ap.add_argument("--map")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    pairs = []
    if a.map:
        with open(a.map, encoding="utf-8") as fh:
            for line in fh:
                line = line.split("#", 1)[0].strip()
                if line:
                    parts = line.split()
                    if len(parts) != 2:
                        sys.exit(f"bad mapping line: {line}")
                    pairs.append(tuple(parts))
    elif a.old and a.new:
        pairs.append((a.old, a.new))
    else:
        ap.error("give OLD NEW or --map")
    mapping = expand(pairs)
    skel_root = os.path.abspath(a.skel_dir)

    md_files = []
    for dp, dns, fns in os.walk(skel_root):
        dns[:] = [d for d in dns if not d.startswith(".")]
        md_files += [os.path.join(dp, f) for f in fns if f.endswith(".md")]
    new_contents = {}
    for f in md_files:
        with open(f, encoding="utf-8") as fh:
            text = fh.read()
        new_loc = mapping.get(f, f)
        text2, n = rewrite(text, f, new_loc, mapping)
        if n or f in mapping:
            new_contents[f] = (new_loc, text2, n)

    for src, dst in sorted(mapping.items()):
        print(f"move {os.path.relpath(src)} -> {os.path.relpath(dst)}")
    for f, (loc, _, n) in sorted(new_contents.items()):
        if n:
            print(f"rewrite {n} link(s) in {os.path.relpath(loc)}")
    if a.dry_run:
        print("(dry run)")
        return
    for src, dst in mapping.items():
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(src, dst)
    for f, (loc, text, _) in new_contents.items():
        with open(loc, "w", encoding="utf-8") as fh:
            fh.write(text)
    # remove now-empty directories left behind
    for src in mapping:
        d = os.path.dirname(src)
        while d.startswith(skel_root) and d != skel_root and os.path.isdir(d) and not os.listdir(d):
            os.rmdir(d)
            d = os.path.dirname(d)


if __name__ == "__main__":
    main()
