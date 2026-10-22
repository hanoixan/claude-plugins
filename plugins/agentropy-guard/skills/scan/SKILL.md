---
name: scan
description: Map this repository's architecture into agentropy-guard's ledger - its components, the important architectural facts with evidence, and erosion signals from history. Run it to set agentropy-guard up in a repository, or when it says the ledger is stale.
disable-model-invocation: true
---

# Scanning the architecture

`GUARD` is `python3 "SKILL_DIR/../../scripts/guard.py"` (`SKILL_DIR` is the folder holding this file).

1. `GUARD init`: creates `.agentropy-guard/` at the git root and keeps `pending.json` and `reports/` out of git.
2. Gather the inputs: `GUARD graph --json`, `GUARD item list --json`, `GUARD signals --history`, and
   `.agentropy-guard/config.json`.
3. Dispatch the `agentropy-guard:architecture-scout` subagent with those four, the path of `guard.py`, and the
   repository root. It returns JSON: `components` (a proposed mapping, only if the config has none or it is wrong),
   `items` (10 to 40 ledger items in the ledger-update skill's format), and `concerns` (cross-cutting concerns done
   differently per component, as finding candidates).
4. If there are erosion candidates (the history signals and the scout's concerns), dispatch the
   `agentropy-guard:erosion-reviewer` subagent on them, as the erosion-check skill says.
5. Show the user, briefly: the component mapping (if proposed), each item's title, category and why it matters, and
   each confirmed finding. Ask once whether to save them: **Save all (Recommended)**, **Let me pick**, **Don't
   save**. With question-refiner installed, exempt the question first (reason "architecture scan").
6. On save: write `components` into `config.json`; write the items to a file and run `GUARD item add --json FILE`;
   record findings with `GUARD finding add --json FILE`; run `GUARD parse`; then `GUARD scanned`.
7. Report in a few lines: how many items and findings were saved, and that agentropy-guard will raise at most one
   architecture note a day, when it is relevant to what the user is doing.

On a rescan, pass the existing items to the scout: it updates them by `id` (unchanged ones stay as they are), adds
new ones, and names any that no longer hold, which you supersede with `GUARD item supersede ID --by NEW` or mark
`"status": "resolved"` through `item add`.
