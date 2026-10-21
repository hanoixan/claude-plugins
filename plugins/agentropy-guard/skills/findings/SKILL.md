---
name: findings
description: List agentropy-guard's architecture erosion findings and record what you decide about each.
argument-hint: "[open|decided]"
disable-model-invocation: true
---

# Erosion findings

`GUARD` is `python3 "SKILL_DIR/../../scripts/guard.py"` (`SKILL_DIR` is the folder holding this file).

The argument is `$ARGUMENTS`: run `GUARD finding list --status decided` when it is `decided`, otherwise
`GUARD finding list --status open`, and show the lines. For an
open finding the user asks about, explain it as the erosion-check skill's warning does, then record their choice with
`GUARD finding decide ID --decision will-fix|fixed|accepted-risk|false-positive`. Candidates still waiting for review
are listed by `GUARD candidates`.
