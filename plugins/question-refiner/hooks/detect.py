#!/usr/bin/env python3
"""SessionStart: when the store has no log yet, look for skel 3.1.0 interview data and tell the agent to ask about
moving it. Silent on any failure."""
import importlib.util
import json
import os
import sys

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "skills", "question-refiner", "scripts",
                      "refiner.py")


def refiner():
    spec = importlib.util.spec_from_file_location("refiner", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def plural(n, one, many):
    return f"{n} {one if n == 1 else many}"


def main():
    try:
        data = json.load(sys.stdin)
        rf = refiner()
        store = rf.store_for(data.get("cwd") or os.getcwd())
        if os.path.exists(os.path.join(store, rf.LOG)):
            return 0
        root = os.path.dirname(store)
        folders = rf.legacy_folders(root)
        parts = []
        for folder in folders:
            records, raters = rf.legacy_summary(os.path.join(root, folder))
            parts.append(f"`{folder}/` ({plural(records, 'record', 'records')}, ratings for "
                         f"{plural(raters, 'person', 'people')})")
    except (Exception, SystemExit):
        return 0
    if not folders:
        return 0
    script = os.path.abspath(SCRIPT)
    text = (f"question-refiner: skel 3.1.0 interview data has not been moved to {rf.STORE}/: {', '.join(parts)}. "
            f"Before anything else this session, ask the user whether to move it. It is an exempt question: run "
            f"`python3 \"{script}\" exempt --question \"<the question>\" --reason \"migrating data\"`, then ask "
            f"it with the choices \"Move it (Recommended)\" and \"Not now\". "
            + ("There is more than one folder: ask which one to move; only one can be imported. "
               if len(folders) > 1 else "")
            + f"On yes, run `python3 \"{script}\" import <folder>`. On no, don't ask again this session.")
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
