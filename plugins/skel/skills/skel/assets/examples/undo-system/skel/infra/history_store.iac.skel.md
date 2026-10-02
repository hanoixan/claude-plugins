---
role: product
---
# infrastructure: history_store

Where persisted undo snapshots live. Framed as infrastructure even if it ends up as a local file, so the decision and its requirements are explicit.

- **Required:** conditional, same condition as [history snapshot](../undo/history_snapshot.data.skel.md).
- **Failure modes:** store unavailable at save time (history is simply not persisted; never block saving the document on it); stale snapshots accumulating.
- **Depends on:** [history snapshot schema](../undo/history_snapshot.data.skel.md)

*UNKNOWN*: Storage medium (sidecar file next to the document, app-data directory, or a cloud object store) and the IaC tool, if any. Kind: blocking. Consequence: placeholder `.iac`; retention and access cannot be implemented. Unlocks: renaming to a real IaC format (e.g. `.tf`) or a local-storage config module.

*UNKNOWN*: Follows [cross-session-undo]. Consequence: this resource is deleted if cross-session undo is not required.

## resource: history_store

- **Data requirements:** one snapshot per document; size typically < 1 MB, capped by `UndoHistory` limit; read once on open, written on save/close; last-write-wins is acceptable; retention: delete when the document is deleted, or after 30 days unused; may contain user content, so it inherits the document's access permissions.
- **Referred by:** [UndoHistory.serialize](../undo/history.code.skel.md#function-serialize)
