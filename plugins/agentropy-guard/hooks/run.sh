#!/usr/bin/env bash
# Runs an agentropy-guard hook with python3. Without python3 it does nothing, so the hook never fails.
here="${BASH_SOURCE[0]%/*}"
command -v python3 >/dev/null 2>&1 || exit 0
exec python3 "$here/hook.py" "$1"
