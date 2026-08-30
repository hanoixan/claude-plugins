#!/usr/bin/env bash
# PostToolUse:Agent — records that this schedule was approved. Runs only after a
# dispatch actually succeeded, which is the only evidence the gate was cleared.
set -uo pipefail
root="${CLAUDE_PROJECT_DIR:-$PWD}"
sched="$root/.claude/plan-batch-schedule.md"
mark="$root/.claude/.plan-batch-approved"
[ -d "$root/.claude" ] || exit 0
if [ -r "$sched" ]; then
  sha256sum "$sched" | cut -d' ' -f1 > "$mark"
else
  echo "NONE" > "$mark"
fi
exit 0
