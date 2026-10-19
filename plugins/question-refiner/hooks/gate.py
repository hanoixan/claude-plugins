#!/usr/bin/env python3
"""PreToolUse on AskUserQuestion: let a question through once it is predicted in the round or exempted.

Prints nothing to allow, a deny with the reason to refuse, and additionalContext alone when it cannot check:
a broken gate never stops the person from being asked.
"""
import datetime
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


def emit(**fields):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", **fields}}))


def main():
    try:
        data = json.load(sys.stdin)
        asked = [q["question"].strip() for q in data["tool_input"]["questions"]]
        rf = refiner()
        state = rf.load(rf.store_for(data.get("cwd") or os.getcwd()))
        if state.problems.errors:
            raise ValueError(f"{rf.STORE}/ does not parse: {state.problems.errors[0]}")
        ok = rf.passable(state, datetime.datetime.now().astimezone())
    except (Exception, SystemExit) as e:
        emit(additionalContext=f"question-refiner could not check this question ({e}); it was let through. "
                               f"Run `refiner.py parse` to see why.")
        return 0
    missing = [q for q in asked if q not in ok]
    if missing:
        script = os.path.abspath(SCRIPT)
        emit(permissionDecision="deny", permissionDecisionReason=(
            "question-refiner: these questions have not been through a round:\n"
            + "".join(f"- {q}\n" for q in missing)
            + f"Write each in {rf.STORE}/{rf.DRAFT}, run `python3 \"{script}\" predict`, then ask it with the "
              f"draft's text word for word. If it trades nothing off (a confirmation, a menu, asking for a name), "
              f"run `python3 \"{script}\" exempt --question \"<text>\" --reason \"<why>\"` first. See the "
              f"question-refiner skill."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
