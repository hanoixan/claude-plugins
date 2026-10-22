---
name: queue
description: Show agentropy-guard's education queue - the important architecture you probably don't know yet, with the scores behind each item.
disable-model-invocation: true
---

# The education queue

`GUARD` is `python3 "SKILL_DIR/../../scripts/guard.py"` (`SKILL_DIR` is the folder holding this file).

Run `GUARD queue --limit 10` and show its lines as they are. A line reads
`ki_0003 priority 0.48 (importance 0.69 x unknown 0.70 x relevance 1) <title>`: importance is how much the item
matters, unknown how likely the user doesn't know it yet, relevance 1.5 when it touches what they are working on.

Then offer: explain one (follow the arch-report skill for the item the user names), mark one known
(`GUARD respond ID --response acknowledged`), or snooze one (`GUARD respond ID --response snoozed --days N`).
`GUARD item get ID` shows an item in full; `GUARD stale` says whether a rescan is due.
