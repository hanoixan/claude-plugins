#!/usr/bin/env bash
# PreToolUse:Agent — state the batching rules at the moment a dispatch is made, where a
# skill body invoked earlier in the session has usually scrolled out of reach.
#
# Rules come from ${CLAUDE_PLUGIN_DATA}/dispatch-rules.txt when that file exists, so a
# local edit survives plugin updates; otherwise from the copy bundled here.
set -uo pipefail

bundled="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/dispatch-rules.txt"
rules="$bundled"
if [ -n "${CLAUDE_PLUGIN_DATA:-}" ] && [ -r "${CLAUDE_PLUGIN_DATA}/dispatch-rules.txt" ]; then
  rules="${CLAUDE_PLUGIN_DATA}/dispatch-rules.txt"
fi

[ -r "$rules" ] || exit 0
command -v jq >/dev/null 2>&1 || exit 0

jq -Rs '{
  suppressOutput: true,
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    additionalContext: .
  }
}' "$rules"
