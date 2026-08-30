---
name: plan-batch-execution
description: Use when about to execute a written implementation plan and deciding how many subagents to dispatch, when tempted to give each task its own agent, or when a code review or full test suite is being placed after every task
---

# Plan Batch Execution

## Overview

You are about to turn a task list into dispatches. The default shape — one subagent per
task, a review after each, a suite run after each — is the expensive one, and it is expensive
in a way that buys nothing.

**Core principle: the unit of dispatch is a chain, not a task.** Sequence lives inside one
agent's context. Parallelism lives between independent chains. Review lives where a defect
would otherwise get built upon.

Reading the dependency graph is the easy part and you already do it well. The decisions that
actually cost money are the three below, and each has a hard rule.

## The Three Rules

### 1. A chain is one dispatch

Tasks in a dependency line — A's output is B's input — go to **one agent, in order**. Not one
agent each. The second agent would rebuild from scratch the context the first one already had,
then wait for a handoff, to produce the same code.

`T1 → T2 → T3 → T4` is **one** dispatch. It is not four, and it is not "four sequential
dispatches for cleanliness".

### 2. Fan-out is one dispatch

k tasks that apply the same shape of edit to different files, with no dependencies among them,
are **one node and one dispatch** — regardless of k.

Three `limit:` annotations in three route files is one agent's work. Six identical config
renames is one agent's work. That each edit is small is the reason to batch them, not a reason
to give each its own agent. Split only when the combined diff exceeds one reviewable pass
(≈15 files / ≈400 lines), and then split in two — never into k.

### 3. A leaf never gets its own dispatch

A task nothing depends on and that is not on the critical path — docs, a changelog, a counter,
a constant — is packed into an existing slot. It never justifies its own agent. Off the
critical path, a separate agent buys **zero** wall clock by construction.

## Do You Dispatch At All?

Count the chains first.

| Shape | Do |
|---|---|
| One chain, ≤5 tasks | **Execute inline.** No dispatch. Nothing can overlap, so an agent buys only context isolation you don't need yet. |
| One chain, >5 tasks or >10 files | **One** dispatch for the whole chain |
| 2+ independent chains | One dispatch per slot, after packing (below) |

A strictly linear plan has no schedule to make. Three tasks in a line is inline work — writing
a batch schedule for it is its own kind of waste.

## Packing

Let `L` = the duration of the **critical path**, the longest chain. Total wall clock can never
fall below `L`, whatever you dispatch.

> Pack every non-critical chain into the fewest slots whose durations each stay ≤ `L`.

Two consequences, both load-bearing:

- **Never split the critical path.** Every split adds a handoff and a context rebuild to the
  one path that sets your wall clock. It is the chain that most needs to stay in one context.
- **Off the critical path, merge freely.** A slot with room takes more work for free. A
  dispatch beyond the packed count costs a full context rebuild and returns nothing.

**Packing needs evidence, not estimates.** Two chains share a slot only when you can point at
something that says one plainly fits in the other's shadow — the plan calls it a one-line
change, it is docs, it is a single constant, it is a leaf. You cannot estimate durations you
have no evidence for, and a wrong guess silently imposes a serial dependency the graph never
required: the second chain sits behind the first for no reason. **When chains look comparable
in size, or you are inferring durations rather than reading them, give each its own slot.**
Six independent chains of similar size are six dispatches, and that is correct. Packing
absorbs obvious slack; it does not balance guesses.

Split a packed slot only if it exceeds ~5–7 tasks, crosses a subsystem boundary, or would
produce a diff too large to localize a failure in.

## Verification: Gates

Three different things get conflated under "testing". They are placed differently.

- **Behavior tests** — written with the code, per behavior, inside the chain, always
  (superpowers:test-driven-development). Never batched, never deferred, not a scheduling
  decision.
- **Scoped suite runs** — the chain agent runs the narrowest suite covering what it just
  changed, continuously as it works. The code is never sitting untested.
- **Gates** — a full-suite run plus a code review dispatch. These are the expensive ones, and
  they go at **gate points** only.

**A gate point is where one chain's output is about to be built on by another chain.** That is
the only place an ungated defect can propagate. Plus one final gate over the whole branch.

```
gates = (hand-off points between chains) + 1 final
```

A chain nothing depends on gets **no separate gate** — its diff joins the final review. Six
independent chains have zero hand-off points: one gate, at the end.

**Batching gates does not reduce what gets reviewed.** Every line is still reviewed, exactly
once, before anything is built on top of it — and every line is covered by scoped tests
continuously while it is written. What a gate-after-every-task adds is not coverage but
*earlier full-suite runs on code nothing depends on yet*, which cannot prevent anything. A
defect that propagates through three tasks propagates across a hand-off; gate the hand-offs and
you catch it at the same place, for one suite run instead of eleven.

**Failure handling:** a chain agent whose scoped suite fails fixes it in place — it holds the
context. Dispatch a fresh fixer only when it reports blocked.

## The Schedule (required output)

Emit this before dispatching. Every section is required, "Deliberately not parallelized"
included.

```markdown
## Batch Schedule — <plan name>

Critical path: T1 → T2 → T5 (est. <L>)
Tasks: N | Chains: C | Slots: D | Hand-off points: H | Gates: H+1

### Wave 1 (concurrent)
**Slot A — CRITICAL PATH** — T1, T2, T4(fan-out batch: 4a–4d), T5
  writes: <files>
  model: <tier>
  scoped suites: run continuously by the chain agent
**Slot B** — T7, T3
  writes: <files>
  model: <tier>
  blocked-on: T3 waits for A:T2 — T7 runs meanwhile

### Gate G1 — A's core, before B builds on it
  full suite + review of A's diff to that point

### Gate FINAL
  full suite + whole-branch review (most capable model), covering every ungated diff

### Deliberately not parallelized
- <task> folded into <slot>: <reason — same file / leaf / off critical path>
```

**Write it to `.claude/plan-batch-schedule.md` in the project root before the first
dispatch.** This plugin's `PreToolUse` hook reads that file and shows it to the user as
the approval prompt for the whole batch: they approve the schedule once, and the
remaining dispatches in it run without further prompting. Edit the schedule and they are
asked again, because the plan they approved has changed.

If the file is absent when a dispatch happens, the hook says so and presents the default
one-agent-per-task shape for approval instead. A missing schedule is therefore visible
rather than silent — which is the point. A one-off subagent that has nothing to do with a
plan can simply be approved.

Then execute it. Use superpowers:subagent-driven-development for the dispatch mechanics —
briefs, report files, review packages, the ledger — substituting **chain** wherever it says
**task**: one brief per chain listing its tasks in order, one report file per chain.

## Red Flags — STOP and re-schedule

- Dispatch count equals task count
- A serial chain split into one dispatch per link
- k same-shape edits given k dispatches because "each is small"
- Docs, a changelog, or any leaf task holding its own dispatch
- A review or a full suite after every task
- More full-suite runs than hand-off points + 1
- Any subagent at all for a single linear chain of ≤5 tasks
- Two concurrent slots listing the same file in their write-sets
- Chains packed together on durations you estimated rather than read

## Common Rationalizations

Every excuse below is quoted or paraphrased from a real controller session that produced a
measurably worse schedule.

| Excuse | Reality |
|--------|---------|
| "Each plan task gets exactly one subagent dispatch — no bundling, no splitting" | This is the default that costs the most. A chain in four agents produces the same code as a chain in one, after three context rebuilds and three handoffs. |
| "Each edit is small enough that a dedicated agent per file is fine" | Small is the argument for batching, not against it. k trivial edits = one dispatch. |
| "Batching reviews costs correctness for speed" | It costs neither. Every line is reviewed once before anything builds on it, and scoped tests run continuously inside the chain. Nothing is reviewed less. |
| "One task, one test, one review — the postmortem mandated it" | The postmortem's defect propagated across a hand-off. Gate the hand-offs and you catch it at the same point for one suite run instead of eleven. Honor the finding, not the ritual. |
| "Scoped runs are additive to the full-suite gate, never a substitute" | The scoped suite covers what changed; the full suite's job is integration. Running it where nothing integrated is a 7-minute no-op. |
| "More agents = faster" | Wall clock floors at the critical path. Agents off it add context rebuilds and nothing else. |
| "These tasks are independent, so parallelize them" | Independent in logic ≠ independent in files. Check write-sets first. |
| "Batching tasks pollutes the agent's context" | Inside a chain that context IS the work — it is the same code. Pollution is unrelated work, not related work. |
| "The plan lists them in order, so they're sequential" | Plan order is narrative order. Only a consumed output is an edge. |
| "It's a 3-task plan but the team likes delegating" | One chain has nothing to overlap. Inline it. |
| "These two chains are probably about the same size, so I'll pack them" | Probably is not evidence. Pack a leaf or a stated one-liner; give comparable chains their own slots. |
| "I'll parallelize everything and resolve conflicts after" | Conflict resolution in the controller costs more than the serialization would have. |

## Worked Example

See [worked-example.md](worked-example.md) — a 12-task plan taken from 12 dispatches / 12
reviews / 12 full-suite runs down to 2 dispatches and 2 gates, with the reasoning at each step.
