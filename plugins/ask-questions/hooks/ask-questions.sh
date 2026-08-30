#!/usr/bin/env bash
# UserPromptSubmit: restate the instruction every turn. A skill body invoked once
# scrolls back and loses to the accumulated habit of assuming; this does not.
#
# Text is read from ${CLAUDE_PLUGIN_DATA}/rules.txt when that file exists, so a local
# edit survives plugin updates; otherwise from the copy bundled here.
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
