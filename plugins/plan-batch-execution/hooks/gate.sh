#!/usr/bin/env bash
# PreToolUse:Agent — show the computed schedule and let the user choose it over the
# default one-agent-per-task shape.
#
# A hook cannot compute a schedule; it can only show one already written. The skill
# writes .claude/plan-batch-schedule.md before dispatching, and this reads it.
#
# Asks once per schedule. The approval marker is written by the PostToolUse hook, so a
# dispatch you decline never records an approval.
set -uo pipefail

root="${CLAUDE_PROJECT_DIR:-$PWD}"
sched="$root/.claude/plan-batch-schedule.md"
mark="$root/.claude/.plan-batch-approved"
max=4000

command -v jq >/dev/null 2>&1 || exit 0

if [ -r "$sched" ]; then
  hash="$(sha256sum "$sched" | cut -d' ' -f1)"
else
  hash="NONE"
fi

# Already approved this exact schedule: stay silent and let normal permissions apply.
if [ -r "$mark" ] && [ "$(cat "$mark" 2>/dev/null)" = "$hash" ]; then
  exit 0
fi

if [ "$hash" = "NONE" ]; then
  reason="No batch schedule was computed for this dispatch.

The plan-batch-execution skill was not consulted, so this is the DEFAULT shape:
one subagent per task, a review after each, a full suite after each. That default
is the expensive one.

Approve to dispatch as-is, or decline and ask for a schedule first."
else
  reason="$(printf 'Approve this batch schedule?\n\nComputed by plan-batch-execution. Declining leaves the default one-agent-per-task shape.\n\n---\n%s' "$(head -c "$max" "$sched")")"
  if [ "$(wc -c < "$sched")" -gt "$max" ]; then
    reason="$reason
[...truncated; full schedule in .claude/plan-batch-schedule.md]"
  fi
fi

jq -n --arg r "$reason" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    permissionDecision: "ask",
    permissionDecisionReason: $r
  }
}'
