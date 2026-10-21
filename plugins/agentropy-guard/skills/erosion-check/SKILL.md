---
name: erosion-check
description: Judge possible architecture erosion in agent-made changes and warn the user so they can decide whether to push back. Use when an agentropy-guard hook reports erosion candidates or open findings, or when you notice agents settling architecture through one-off deals.
---

# Erosion: judging and warning

`GUARD` is `python3 "SKILL_DIR/../../scripts/guard.py"` (`SKILL_DIR` is the folder holding this file).

Agents settle choices among themselves at almost no cost, so the friction that once forced clean boundaries is gone.
The architecture drifts toward whatever agents found locally convenient. The mechanisms (from the source analysis):

1. Boundaries follow where humans must decide, not the module plan.
2. Cheap coordination breeds point-to-point deals: adapters, mappers, duplicate models.
3. Contracts become explicit but churn.
4. Conceptual integrity erodes: cross-cutting concerns diverge per component.
5. The agent's "does the human need this?" filter quietly makes design decisions.
6. Each component grows its own façade.
7. The communication topology is configuration, so it can be designed on purpose.

## Reviewing candidates

When a hook says there are candidates: run `GUARD candidates`, dispatch the `agentropy-guard:erosion-reviewer`
subagent with them, the repository root and the path of `guard.py`, and record each finding it confirms with
`GUARD finding add --json -` (fields: `signal`, `severity`, `description`, `evidence`, `components`,
`conway_mechanism`, `suggested_countermove`, `cost`, and the candidate's `key`). Then `GUARD candidates --clear`.
`GUARD signals --paths FILE ...` runs the detectors on any files by hand.

## Warning the user

Warn about at most one high-severity finding per session, when the hook allows it, at the end of your reply:

> ⚠️ **Architecture drift:** this is the third adapter between `orders` and `billing` (`billing/sync/customerAdapter.ts`,
> …). Each was a local fix; together they mean the two no longer share a Customer model. A shared contract in
> `contracts/customer.ts` would replace all three (about 1–2 hours). Fix now, note it for later, accept it, or call
> it a false positive?

One sentence on what is happening, with file paths; the mechanism in plain words; a countermove and its rough cost;
then the four choices: **Fix now**, **Note it, later**, **Accept this**, **False positive**. With question-refiner
installed, ask it as an exempt question (reason "architecture warning"). Record the answer with
`GUARD finding decide ID --decision will-fix|accepted-risk|false-positive` (`will-fix` for both now and later; `fixed`
once it is done), then run `GUARD warned --session ID` with the session id the hook gave.

At the start of a session, the hook may ask you to list open medium and low findings: a short block, one line each,
and one question asking which, if any, to act on.
