#!/usr/bin/env bash
# UserPromptSubmit: one line, every turn. The rules themselves stay in the skill;
# this only guarantees the skill is remembered before the dispatch count is chosen.
set -uo pipefail
bundled="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/pointer.txt"
p="$bundled"
[ -n "${CLAUDE_PLUGIN_DATA:-}" ] && [ -r "${CLAUDE_PLUGIN_DATA}/pointer.txt" ] && p="${CLAUDE_PLUGIN_DATA}/pointer.txt"
[ -r "$p" ] || exit 0
command -v jq >/dev/null 2>&1 || exit 0
jq -Rs '{suppressOutput:true, hookSpecificOutput:{hookEventName:"UserPromptSubmit", additionalContext:.}}' "$p"
