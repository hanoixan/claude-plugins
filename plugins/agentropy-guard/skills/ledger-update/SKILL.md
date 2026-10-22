---
name: ledger-update
description: Add or refresh agentropy-guard ledger items - the important architectural facts of this repository. Use when you make or discover an architectural decision (a boundary, contract, data model, cross-cutting rule, runtime topology or invariant), and in the scan skill.
---

# Writing ledger items

`GUARD` is `python3 "SKILL_DIR/../../scripts/guard.py"` (`SKILL_DIR` is the folder holding this file).

An item is one architectural fact someone changing this code needs to know. When you make such a decision yourself,
record it with `"origin": "agent-decision"`: those are exactly the ones the user never saw.

```json
{
  "title": "Orders and Billing each define their own Customer model",
  "category": "data-model",
  "summary": "Two Customer schemas; billing/sync maps between them.",
  "details": "Longer explanation, consequences.",
  "evidence": [{"type": "file", "path": "orders/models/customer.ts"}, {"type": "commit", "sha": "abc123"}],
  "components": ["orders", "billing"],
  "importance_factors": {"blast_radius": 0.9, "cross_cutting": 0.7, "irreversibility": 0.6},
  "origin": "agent-decision"
}
```

- `category`: boundary, contract, data-model, cross-cutting, dependency, decision, integration, runtime-topology,
  invariant. `origin`: agent-decision, human-decision, discovered, unknown.
- Factors, 0 to 1: `blast_radius` (how much depends on it: 0.2 one file, 0.5 a component, 0.9 most of the system);
  `cross_cutting` (spans components, or touches security, data or performance); `irreversibility` (public API,
  persisted schema or external contract is high). The script adds `change_frequency` from git and computes
  `importance`.
- Evidence is files (`path`, optional `lines`), commits (`sha`) or PRs (`url`); at least one.

Save with `GUARD item add --json FILE` (or `-` and stdin); to update, include the item's `id` and only the changed
fields. `GUARD item list` and `GUARD item get ID` read the ledger; `GUARD item supersede OLD --by NEW` retires one;
`GUARD item refresh` recomputes change frequency; `GUARD parse` checks every file.
