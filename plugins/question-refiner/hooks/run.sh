#!/usr/bin/env bash
# Runs a question-refiner hook with python3. Without python3, the gate lets the question through and says why;
# the session-start check stays silent. Uses no other command, since PATH may hold nothing else.
here="${BASH_SOURCE[0]%/*}"
if ! command -v python3 >/dev/null 2>&1; then
  if [ "${1:-}" = gate.py ]; then
    printf '%s\n' '{"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": "question-refiner needs python3, which is not on PATH, so this question was let through unchecked. Ask directly, and tell the user that question-refiner needs python3."}}'
  fi
  exit 0
fi
exec python3 "$here/$1"
