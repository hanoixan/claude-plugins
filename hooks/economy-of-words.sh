#!/usr/bin/env bash
# UserPromptSubmit: re-inject the rules at the end of every turn's context, where
# an invoked skill's body cannot reach once it has scrolled back in the history.
#
# Rules are read from ${CLAUDE_PLUGIN_DATA}/rules.txt when that file exists, so a
# local edit survives plugin updates; otherwise from the copy bundled here.
set -uo pipefail

bundled="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/rules.txt"
rules="$bundled"
if [ -n "${CLAUDE_PLUGIN_DATA:-}" ] && [ -r "${CLAUDE_PLUGIN_DATA}/rules.txt" ]; then
  rules="${CLAUDE_PLUGIN_DATA}/rules.txt"
fi

[ -r "$rules" ] || exit 0
command -v jq >/dev/null 2>&1 || exit 0

jq -Rs '{
  suppressOutput: true,
  hookSpecificOutput: {
    hookEventName: "UserPromptSubmit",
    additionalContext: .
  }
}' "$rules"
