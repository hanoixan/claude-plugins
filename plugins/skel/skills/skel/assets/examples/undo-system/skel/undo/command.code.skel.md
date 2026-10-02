# module: command

Defines the reversible edit abstraction. Every user-visible edit in the host is expressed as a `Command`; anything not expressed this way is invisible to undo, which is the most common source of undo bugs, so the host binding must route all edits through commands.

- **Owns:** the `Command` contract.
- **Access:** imported by host feature code (to implement commands) and by the undo modules.
- **Required:** always.
- **Failure modes:** a command whose `revert` is not an exact inverse of `apply` silently corrupts the document after undo; mitigate with round-trip tests (apply → revert → compare snapshot).
- **Depends on:** [DocumentTarget](./document_target.code.skel.md#class-documenttarget)
- **Referred by:** [Transaction](./transaction.code.skel.md#class-transaction)
- **Referred by:** [UndoHistory](./history.code.skel.md#class-undohistory)
- **Unknowns:** none

## class: Command

An abstract base (or interface/trait) for reversible edits. Implementations capture *everything* needed to revert at apply time (e.g. the old value), never by re-reading the document during revert.

- **Inputs:** implementation-specific payload (the edit's parameters).
- **State changes:** after a successful `apply`, holds whatever is needed for `revert`. Invariant: `apply` and `revert` alternate, starting with `apply`.
- **Owns:** its captured before/after data.
- **Access:** created by host code, then handed to `UndoHistory.push`; after that only history calls its methods.

### function: apply

- **Inputs:** `target`: [DocumentTarget](./document_target.code.skel.md#class-documenttarget).
- **Returns:** success or failure.
- **State changes:** mutates the document through `target`; records revert data; calls `target.notify_changed` once.
- **Access:** called only by `UndoHistory` (initial apply and redo) or by `Transaction.apply`.
- **Failure modes:** on failure it must leave the document unchanged (all-or-nothing).

### function: revert

- **Inputs:** `target`.
- **Returns:** success or failure.
- **State changes:** restores the document to its pre-`apply` state; calls `target.notify_changed` once.
- **Access:** called only by `UndoHistory.undo` or `Transaction.revert`.

### function: merge_with

Optional coalescing hook. Lets consecutive typing become one undo step.

- **Inputs:** `next`: the command about to be pushed; `elapsed`: time since this command was applied.
- **Returns:** a merged command, or nothing if not mergeable.
- **State changes:** none; must not mutate either input.
- **Access:** called by `UndoHistory.push` only.

```text
merge rule example: InsertText("ab", at 3) + InsertText("c", at 5) within 1s -> InsertText("abc", at 3)
```

### function: describe

- **Inputs:** none.
- **Returns:** a short human-readable label ("Insert text", "Delete 3 shapes") for menus.
- **State changes:** none.
- **Access:** called by UI via `UndoHistory.peek_labels`.
