#!/usr/bin/env python3
"""PreToolUse on AskUserQuestion: let a question through once it is predicted in the round or exempted.

Prints nothing to allow, a deny with the reason to refuse, and additionalContext alone when it cannot check:
a broken gate never stops the person from being asked.
"""
import datetime
import difflib
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


def unmark(q):
    """The question without the `<!> ` high-stakes mark it is asked with."""
    return q[4:].strip() if q.startswith("<!> ") else q


def hint(q, state):
    """Why a question failed, when the round says more than "not drafted"."""
    drafted = [r.question.strip() for r in state.draft or []]
    if q in drafted:
        return "in the round but not predicted yet"
    near = difflib.get_close_matches(q, drafted + [e.question for e in state.exempt], n=1, cutoff=0.8)
    return f"closest in the round: `{near[0]}`" if near else ""


def main():
    try:
        data = json.load(sys.stdin)
        asked = [unmark(q["question"].strip()) for q in data["tool_input"]["questions"]]
        rf = refiner()
        store = rf.store_for(data.get("cwd") or os.getcwd())
        state = rf.load(store)
        errors = state.problems.errors
        if errors and all(e.startswith(rf.DRAFT + ":") for e in errors):
            emit(permissionDecision="deny", permissionDecisionReason=(
                f"question-refiner: {os.path.join(store, rf.DRAFT)} does not parse, so no question in it counts as "
                f"predicted:\n" + "".join(f"- {e}\n" for e in errors[:5])
                + "Fix the round, run `refiner.py predict` again, then ask."))
            return 0
        if errors:
            raise ValueError(f"{rf.STORE}/ does not parse: {errors[0]}")
        ok = rf.passable(state, datetime.datetime.now().astimezone())
    except (Exception, SystemExit) as e:
        emit(additionalContext=f"question-refiner could not check this question ({type(e).__name__}: {e}); it "
                               f"was let through. Run `python3 \"{os.path.abspath(SCRIPT)}\" parse` to see why.")
        return 0
    missing = [q for q in asked if q not in ok]
    if missing:
        script = os.path.abspath(SCRIPT)
        notes = {q: hint(q, state) for q in missing}
        emit(permissionDecision="deny", permissionDecisionReason=(
            "question-refiner: these questions have not been through a round:\n"
            + "".join(f"- {q}\n" + (f"  ({notes[q]})\n" if notes[q] else "") for q in missing)
            + (f"There is no weights.md yet: choose the domains first with `python3 \"{script}\" domains add "
               f"DOMAIN ...` (see the skill's first-use section).\n" if state.weights_lines is None else "")
            + f"Write each in {os.path.join(store, rf.DRAFT)}, run `python3 \"{script}\" predict`, then ask it "
              f"with the draft's text word for word, without its `<probe>` mark. If it trades nothing off (a "
              f"confirmation, a menu, asking for a name), run `python3 \"{script}\" exempt --question \"<text>\" "
              f"--reason \"<why>\"` first. See the question-refiner skill."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
