# Worked Example — 12 tasks, 12 dispatches down to 2

The plan: add API-key authentication to a web service.

| # | Task | Writes |
|---|---|---|
| T1 | `api_keys` table migration | `db/migrations/*` |
| T2 | `ApiKey` model + repository | `src/models/api_key.ts`, `src/repos/api_key_repo.ts` |
| T3 | Key hashing utility | `src/util/hash.ts` |
| T4 | Auth middleware verifying a key | `src/middleware/auth.ts` |
| T5 | Wire middleware into the router | `src/server/router.ts` |
| T6 | `POST /keys` endpoint | `src/routes/keys.ts` |
| T7 | `DELETE /keys/:id` endpoint | `src/routes/keys.ts` |
| T8–T11 | Add `requires_auth` to 4 existing route files | `src/routes/{a,b,c,d}.ts` |
| T12 | Update README + CHANGELOG | `README.md`, `CHANGELOG.md` |

## Graph

```
T1 → T2 → T4 → T5 → {T8, T9, T10, T11}
T3 → T4
T2 → T6, T2 → T7
T12  (nothing)
```

T6 and T7 both write `src/routes/keys.ts`: logically independent, physically conflicting, so
they are ordered. Neither is on the critical path, so serialize rather than reach for a
worktree.

## Chains

**Critical path:** `T1 → T2 → T4 → T5 → {T8–T11}`. That is Chain A, one agent, start to
finish — never split, because every split lands on the path that sets the wall clock.

Applying the three rules:

- **Rule 1 (chain = one dispatch):** T1, T2, T4, T5 are a dependency line. One agent, four
  tasks in order. T3's only consumer is T4, so it joins the front of A rather than paying a
  context rebuild to deliver one utility file.
- **Rule 2 (fan-out = one dispatch):** T8–T11 are four identical annotation edits. **One**
  node, one dispatch. Four small edits is the reason to batch them, not four reasons to
  dispatch. They sit at A's tail, where nothing waits on them.
- **Rule 3 (leaf never dispatches alone):** T12 is docs — nothing depends on it, and it is off
  the critical path. It packs into Slot B.

## Packing

`L` = Chain A ≈ 6 units. Chain B (T6→T7) ≈ 2, Chain C (T12) ≈ 1. Both fit under `L` with slack,
so they pack into **one** slot. Two dispatches.

B's endpoints are blocked until A produces the repository at T2 — a dependency on **one task
inside A**, not on all of A. Order the slot so its unblocked work runs first: T12 leads, and by
the time it finishes T2 has landed. No idle, no barrier.

A third dispatch here would leave `L` unchanged and cost one more context rebuild.

## Gates

One hand-off point: Slot B builds on A's repository. So:

```
gates = 1 hand-off + 1 final = 2
```

Two full-suite runs, two review dispatches. Chain A's tail (T5, T8–T11) has nothing downstream
of it, so it gets no separate gate — its diff joins the final review. Behavior tests are still
written per task under TDD, and each agent runs its scoped suite continuously.

## The schedule

```markdown
## Batch Schedule — api-key-auth

Critical path: T1 → T2 → T4 → T5 → T8–11 (est. 6 units)
Tasks: 12 | Chains: 3 | Slots: 2 | Hand-off points: 1 | Gates: 2

### Wave 1 (concurrent)
**Slot A — CRITICAL PATH** — T3, T1, T2, T4, T5, T8–11 (fan-out batch)
  writes: src/util/hash.ts, db/migrations/*, src/models/api_key.ts,
          src/repos/api_key_repo.ts, src/middleware/auth.ts, src/router.ts,
          src/routes/{a,b,c,d}.ts
  model: standard (multi-file integration)
  scoped suites: continuous, by the chain agent
  signal: report when T2 lands

**Slot B** — T12, then T6, then T7
  writes: README.md, CHANGELOG.md, src/routes/keys.ts
  model: cheap (mechanical, complete specs)
  blocked-on: T6/T7 wait for A:T2 — T12 runs meanwhile
  scoped suites: continuous, by the chain agent

### Gate G1 — A's model+repo, before B's endpoints build on it
  full suite + review of A's diff through T2

### Gate FINAL
  full suite + whole-branch review (most capable model), covering every ungated diff

### Deliberately not parallelized
- T3 folded into A: its only consumer is T4
- T7 serialized behind T6: both write src/routes/keys.ts; neither is critical, so no worktree
- T8–T11 batched: four identical edits, one dispatch, one diff
- T12 packed into B: leaf, off the critical path — a third agent buys 0 wall clock
```

## What the alternatives cost

**One subagent per task:** 12 dispatches, 12 context rebuilds, 12 reviews, 12 full-suite runs —
and T6/T7 dispatched concurrently would have clobbered each other in `src/routes/keys.ts`.

**Wave-by-wave parallelism:** five barriers, each costing its slowest member, with two waves
holding a single task while everything else idles — plus the same T6/T7 collision.

**Everything inline:** no collisions and no dispatch toll, but Slot B's work sits on the clock
instead of running alongside A. Correct for a plan with one chain; wasteful once there are two.
