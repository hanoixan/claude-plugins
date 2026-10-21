#!/usr/bin/env python3
"""Runs one agentropy-guard hook: `hook.py EVENT`, the hook's JSON on stdin. Silent on any failure, so a broken
hook never gets in the person's way."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))


def main():
    try:
        import guard
        data = json.load(sys.stdin)
        out = guard.HOOKS[sys.argv[1]](data if isinstance(data, dict) else {})
    except (Exception, SystemExit):
        return 0
    if out:
        print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
