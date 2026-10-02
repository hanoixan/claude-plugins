# module: history

The undo/redo stacks and the only public entry point the host interacts with at runtime.

- **Owns:** the undo stack, redo stack, open-transaction state, memory budget accounting.
- **Access:** one `UndoHistory` instance per open document, owned by the host's document controller.
- **Required:** always.
- **Failure modes:** unbounded memory growth if `limit` is not enforced; nested `begin_group` without `end_group` leaves history stuck in grouping mode (guard with depth counter and a debug assertion).
- **Depends on:** [Command](./command.code.skel.md#class-command)
- **Depends on:** [Transaction](./transaction.code.skel.md#class-transaction)
- **Referred by:** [bind_undo](../integration/host_binding.code.skel.md#function-bind_undo)

## class: UndoHistory

- **Inputs:** `target` (DocumentTarget); `limit`: max steps or bytes retained.
- **State changes:** invariant: the redo stack is empty immediately after any `push`; at most one open transaction at a time (nested begin/end counts depth).
- **Owns:** all commands pushed to it.
- **Access:** host document controller holds it; UI calls `undo`/`redo`/`can_undo`/`can_redo`/`peek_labels`.

*UNKNOWN*: Whether `limit` is counted in steps or approximate bytes. Kind: blocking. Consequence: commands may need a `size_estimate` method. Unlocks: final `Command` interface and memory tests.

*UNKNOWN*: [default-limit] Default value of `limit` when the host passes none. Kind: local. Proposed: 1000 steps. Consequence: memory use under default settings is unspecified. Unlocks: a constant and its test.

### function: push

- **Inputs:** `command` (not yet applied).
- **Returns:** success or failure.
- **State changes:** applies the command; on success either merges into the top entry (via `Command.merge_with`) or pushes it; clears redo; enforces `limit` by dropping oldest entries. Inside an open group, appends to the open `Transaction` instead.
- **Access:** host feature code, for every edit.
- **Failure modes:** apply failure: nothing is recorded, error returned to caller.

### function: undo

- **Inputs:** none.
- **Returns:** success, failure, or "nothing to undo".
- **State changes:** reverts top of undo stack, moves it to redo stack. On revert failure, the entry and the whole redo stack are discarded (the document state is no longer trustworthy for redo).
- **Access:** UI / keyboard shortcut via host binding. Not allowed while a group is open.

### function: redo

- **Inputs:** none.
- **Returns:** success, failure, or "nothing to redo".
- **State changes:** re-applies top of redo stack, moves it back to undo stack.
- **Access:** as `undo`.

### function: begin_group

- **Inputs:** a label.
- **Returns:** nothing.
- **State changes:** opens a [Transaction](./transaction.code.skel.md#class-transaction) (or increments depth if one is open).
- **Access:** host code around compound edits; must be paired with `end_group` in a finally/defer block.

### function: end_group

- **Inputs:** none.
- **Returns:** nothing.
- **State changes:** decrements depth; at zero, closes the transaction and pushes it (empty transactions are dropped).
- **Access:** as `begin_group`.

### function: peek_labels

- **Inputs:** none.
- **Returns:** the `describe()` labels of the next undo and next redo entries, or nothing.
- **State changes:** none.
- **Access:** UI menus ("Undo Insert text").

### function: serialize

Writes history to the persisted snapshot format, if persistence is enabled.

- **Inputs:** none.
- **Returns:** a snapshot conforming to the schema.
- **State changes:** none.
- **Access:** host binding on document save/close.
- **Depends on:** [history snapshot](./history_snapshot.data.skel.md)
- **Depends on:** [history_store](../infra/history_store.iac.skel.md#resource-history_store)

*UNKNOWN*: Whether commands can be serialized at all (some may hold host object references). Kind: blocking. Consequence: persistence may only be partial; non-serializable commands truncate the saved history at that point. Unlocks: deciding the snapshot schema's `payload` contract.
