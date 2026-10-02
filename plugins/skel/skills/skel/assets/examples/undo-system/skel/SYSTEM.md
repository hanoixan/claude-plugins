# System: Undo/Redo

A portable undo/redo subsystem for any application that edits a document-like model. It is specified abstractly: every stand-in uses a placeholder extension (`.code`, `.data`, `.iac`) until the host project's language, platform and layout are known. See the adaptation checklist at the end.

## Scope

In scope: recording reversible edits as commands, grouping edits into transactions, linear undo/redo, coalescing rapid edits (typing), memory limits, optional persistence of history across sessions.

Out of scope: branching (tree) history, collaborative/multi-user undo (needs OT/CRDT; see unknown below), selection/caret restoration beyond what commands record.

## Glossary

- **Command**: a reversible unit of change with `apply` and `revert`.
- **Transaction**: an ordered group of commands undone/redone as one step.
- **History**: the linear undo stack and redo stack, plus a cursor.
- **Document target**: whatever the host lets commands mutate.
- **Coalescing**: merging a new command into the previous one (e.g. consecutive keystrokes).

## Global decisions

*UNKNOWN*: [language] Implementation language and runtime. Kind: blocking. Consequence: all stand-ins stay abstract (`.code`); signatures are given in meaning, not types. Unlocks: renaming stand-ins to real extensions with `skel_mv.py --map` and stating concrete types.

*UNKNOWN*: Whether the host is collaborative (multiple writers to one document). Kind: blocking. Consequence: if yes, linear history is wrong and commands must be transformable; this spec would need a redesign of `Command`. Unlocks: confirming this single-writer design.

- Concurrency: all history operations happen on the host's single edit thread / event loop. Commands are never applied concurrently.
- Errors: a command that fails to apply or revert must leave the document unchanged and report failure; history then discards that step (see failure modes in [history](./undo/history.code.skel.md)).

## Test strategy

- Levels in this plan: behaviour tests of the undo core against a fake `DocumentTarget` ([history_test](./undo/history_test.code.skel.md)).
- Left out on purpose: tests of the host binding. Shortcuts and menus are exercised by the host application's own interface tests.


## Entry points

- [UndoHistory](./undo/history.code.skel.md#class-undohistory): the object the host owns.
- [Command](./undo/command.code.skel.md#class-command): what host features implement for each kind of edit.
- [Host binding](./integration/host_binding.code.skel.md): how the host wires shortcuts and dirty-state.

## Adaptation checklist

1. Answer the unknowns above and in `skel_check.py unknowns skel/`.
2. Write a mapping file from placeholder paths to real project paths and run `skel_mv.py`.
3. Replace meaning-only signatures with concrete types; delete resolved unknowns.
4. Run `skel_check.py check skel/` until clean, then `order` to plan implementation.
