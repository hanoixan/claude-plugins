# module: transaction

Groups several commands into one undoable step, e.g. "paste" = delete selection + insert. A transaction is itself a command (composite pattern), so history doesn't special-case it.

- **Owns:** the `Transaction` composite.
- **Access:** created only by `UndoHistory.begin_group`; host code never constructs one directly.
- **Required:** always.
- **Failure modes:** partial failure mid-apply; see `apply`.
- **Depends on:** [Command](./command.code.skel.md#class-command)
- **Referred by:** [UndoHistory.begin_group](./history.code.skel.md#function-begin_group)
- **Unknowns:** none

## class: Transaction

- **Inputs:** a label for `describe`.
- **State changes:** holds an ordered list of child commands; closed after `end_group`, after which it is immutable.
- **Owns:** its child commands.
- **Access:** via `UndoHistory` only.

### function: apply

- **Inputs:** `target`.
- **Returns:** success or failure.
- **State changes:** applies children in order. If child *k* fails, reverts children *k-1 … 0* in reverse order, then reports failure (all-or-nothing).
- **Access:** `UndoHistory.redo`.

### function: revert

- **Inputs:** `target`.
- **Returns:** success or failure.
- **State changes:** reverts children in reverse order.
- **Access:** `UndoHistory.undo`.
