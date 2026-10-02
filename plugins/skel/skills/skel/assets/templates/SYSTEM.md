# System: <name>

<Purpose and one-paragraph overview.>

## Scope

In scope: ...
Out of scope: ...

## Glossary

- **<Term>**: <definition>

## Global decisions

- Language/runtime: <decided value> or *UNKNOWN*: [language] ... Kind: blocking. Consequence: ... Unlocks: ...
- Platform/deployment: ...
- Concurrency model: ...
- Error-handling policy: ...
- Logging/observability: ...

## Test strategy

- Levels in this plan: <unit | integration | end-to-end>, and what each covers.
- Left out on purpose: <level or kind of test, and why>.

## Entry points

- [<Main symbol>](<./path.ext.skel.md#class-name>): <role>

## Adaptation checklist (abstract systems only)

1. Answer the unknowns (`skel_check.py unknowns skel/`).
2. Map placeholder paths to real paths and run `skel_mv.py skel --map map.txt`.
3. Make signatures concrete; delete resolved unknowns.
4. Run `skel_check.py check skel/`, then `order`.
